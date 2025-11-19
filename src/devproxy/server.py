import asyncio
import time
from typing import Dict
from dataclasses import dataclass
import logging

# ==================== PRODUCTION METRICS ====================
# Global counters (thread-safe because asyncio is single-threaded)
request_count = 0  # Total requests handled
error_count = 0    # Total errors encountered

# ==================== SIMPLE LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== HTTP DATA STRUCTURES ====================
@dataclass
class HTTPRequest:
    """HTTP request representation"""
    method: str
    path: str
    version: str
    headers: Dict[str, str]
    body: bytes


# ==================== SAFETY LIMITS (RFC 7230) ====================
class HTTPLimits:
    """HTTP safety limits"""
    MAX_REQUEST_LINE = 4096      # 4KB max request line
    MAX_HEADER_SIZE = 8192       # 8KB max per header  
    MAX_HEADERS = 100            # Max 100 headers
    MAX_TOTAL_HEADERS = 65536    # 64KB total headers
    MAX_BODY_SIZE = 10_000_000   # 10MB max body
    REQUEST_TIMEOUT = 5.0        # 5s for request line
    HEADER_TIMEOUT = 10.0        # 10s for headers
    BODY_TIMEOUT = 30.0          # 30s for body


# ==================== REQUEST PARSER ====================
async def parse_request_production(reader: asyncio.StreamReader, client_addr: tuple) -> HTTPRequest:
    """Parse HTTP request - always returns HTTPRequest or raises exception"""
    limits = HTTPLimits()
    total_size = 0
    header_count = 0
    
    # Request line with timeout
    try:
        request_line_bytes = await asyncio.wait_for(reader.readline(), timeout=limits.REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        raise ValueError(f"Request line timeout after {limits.REQUEST_TIMEOUT}s")
        
    if not request_line_bytes:
        raise ValueError("Client disconnected before sending request line")
        
    if len(request_line_bytes) > limits.MAX_REQUEST_LINE:
        raise ValueError(f"Request line too long: {len(request_line_bytes)} bytes")
        
    request_line = request_line_bytes.decode('utf-8').strip()
    logger.info("Request: %s from %s", request_line, client_addr)
    
    # Parse request line
    try:
        method, path, version = request_line.split(" ", 2)
        if version not in ["HTTP/1.0", "HTTP/1.1"]:
            raise ValueError(f"Unsupported HTTP version: {version}")
    except ValueError as e:
        raise ValueError(f"Malformed request line: {request_line}") from e
        
    # Headers with safety limits
    headers = {}
    while True:
        try:
            header_line_bytes = await asyncio.wait_for(reader.readline(), timeout=limits.HEADER_TIMEOUT)
        except asyncio.TimeoutError:
            raise ValueError(f"Header timeout after {limits.HEADER_TIMEOUT}s")
            
        if not header_line_bytes:
            raise ValueError("Client disconnected mid-headers")
            
        total_size += len(header_line_bytes)
        if total_size > limits.MAX_TOTAL_HEADERS:
            raise ValueError(f"Headers too big: {total_size} bytes")
            
        header_line = header_line_bytes.decode('utf-8').strip()
        
        if header_line == "":
            break
            
        if len(header_line) > limits.MAX_HEADER_SIZE:
            raise ValueError(f"Header too long: {len(header_line)} bytes")
            
        header_count += 1
        if header_count > limits.MAX_HEADERS:
            raise ValueError(f"Too many headers: {header_count}")
            
        if ": " not in header_line:
            logger.warning("Bad header format: %s", header_line)
            continue
            
        key, value = header_line.split(": ", 1)
        headers[key] = value
        
    logger.info("Headers: %d headers, %d bytes from %s", header_count, total_size, client_addr)
    
    # Body with size limits
    body = b""
    if "Content-Length" in headers:
        try:
            content_length = int(headers["Content-Length"])
            if content_length > limits.MAX_BODY_SIZE:
                raise ValueError(f"Body too big: {content_length} bytes")
                
            body = await asyncio.wait_for(
                reader.readexactly(content_length),
                timeout=limits.BODY_TIMEOUT
            )
            
            logger.info("Body: %d bytes from %s", len(body), client_addr)
            
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid Content-Length: {headers['Content-Length']}")
            raise
        except asyncio.TimeoutError:
            raise ValueError(f"Body timeout after {limits.BODY_TIMEOUT}s")
        except asyncio.IncompleteReadError:
            raise ValueError("Client disconnected before sending full body")
    
    return HTTPRequest(method, path, version, headers, body)


# ==================== RESPONSE GENERATORS ====================
def generate_response(request: HTTPRequest) -> bytes:
    """Generate HTTP response"""
    response_body = f"Hello from DevProxy! You requested: {request.method} {request.path}"
    return response_body.encode('utf-8')


async def send_response(writer: asyncio.StreamWriter, body: bytes) -> None:
    """Send HTTP response"""
    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n"
        b"\r\n" + 
        body
    )
    
    writer.write(response)
    await writer.drain()


async def send_error_response(writer: asyncio.StreamWriter, status: int, message: str) -> None:
    """Send HTTP error response"""
    body = f"Error {status}: {message}".encode('utf-8')
    
    response = (
        f"HTTP/1.1 {status} ".encode() +
        {400: "Bad Request", 408: "Request Timeout", 500: "Internal Server Error"}.get(status, "Unknown").encode() + b"\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n"
        b"\r\n" +
        body
    )
    
    writer.write(response)
    await writer.drain()


# ==================== MAIN CLIENT HANDLER ====================
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle client - never crashes, always cleans up"""
    global request_count, error_count
    
    client_addr = writer.get_extra_info("peername")
    request_count += 1
    start_time = time.time()
    
    # SAFETY: Initialize variables
    request = None
    method = "UNKNOWN"
    path = "UNKNOWN"
    
    logger.info("Client connected: %s (total: %d)", client_addr, request_count)
    
    try:
        # Parse request (can fail completely)
        logger.debug("Starting request parse for %s", client_addr)
        request = await parse_request_production(reader, client_addr)
        
        # Only set these if parsing succeeded
        method = request.method
        path = request.path
        
        # Generate and send response
        logger.debug("Generating response for %s %s", method, path)
        response = generate_response(request)
        await send_response(writer, response)
        
        # Success metrics
        duration = time.time() - start_time
        logger.info("Request completed: %s %s (%.3fs)", method, path, duration)
        
    except ValueError as e:
        # Handle parsing errors gracefully
        error_count += 1
        logger.warning("Bad request from %s: %s", client_addr, e)
        
        # Send proper error response
        error_msg = str(e)
        error_response = (
            f"HTTP/1.1 400 Bad Request\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(error_msg)}\r\n"
            f"Connection: close\r\n"
            f"\r\n{error_msg}"
        ).encode()
        
        writer.write(error_response)
        await writer.drain()
        logger.info("Error response sent to %s: %s", client_addr, error_msg)
        
    except asyncio.TimeoutError as e:
        # Handle timeouts specifically
        error_count += 1
        logger.warning("Timeout from %s: %s", client_addr, e)
        
        timeout_response = (
            b"HTTP/1.1 408 Request Timeout\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"Content-Length: 15\r\n"
            b"Connection: close\r\n"
            b"\r\nRequest Timeout"
        )
        
        writer.write(timeout_response)
        await writer.drain()
        logger.info("Timeout response sent to %s", client_addr)
        
    except Exception as e:
        # Last resort
        error_count += 1
        logger.error("Unexpected error from %s: %s", client_addr, e, exc_info=True)
        
        # Don't expose internal errors to clients
        internal_error = (
            b"HTTP/1.1 500 Internal Server Error\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            b"Content-Length: 25\r\n"
            b"Connection: close\r\n"
            b"\r\nInternal Server Error"
        )
        
        writer.write(internal_error)
        await writer.drain()
        logger.info("Internal error response sent to %s", client_addr)
        
    finally:
        # GUARANTEED cleanup
        logger.info("Disconnecting %s (requests: %d, errors: %d)", 
                   client_addr, request_count, error_count)
        writer.close()
        await writer.wait_closed()


# ==================== MAIN FUNCTION ====================
async def main():
    """Main function"""
    global request_count, error_count
    
    logger.info("Starting DevProxy server on port 8888")
    logger.info("Initial metrics - requests: %d, errors: %d", request_count, error_count)
    
    server = await asyncio.start_server(
        handle_client, 
        "localhost", 
        8888,
        reuse_address=True,
        backlog=128
    )
    
    addr = server.sockets[0].getsockname()
    logger.info("Server started on %s", addr)
    
    try:
        async with server:
            await server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user (final: requests=%d, errors=%d)", 
                   request_count, error_count)
    except Exception as e:
        logger.error("Server crashed: %s", e, exc_info=True)
        raise


# ==================== STARTUP ====================
if __name__ == "__main__":
    asyncio.run(main())