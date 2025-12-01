import asyncio
import os
import time
from typing import Dict
from dataclasses import dataclass
import logging
from .parser import parse_request_production, HTTPRequest
from .config import Config

# ==================== PROXY CONFIGURATION ====================
UPSTREAM_HOST = os.getenv("UPSTREAM_HOST", "localhost")
UPSTREAM_PORT = int(os.getenv("UPSTREAM_PORT", "3001"))
PROXY_PREFIX = "/proxy"

# ==================== PRODUCTION METRICS ====================
class Metrics:
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self._lock = asyncio.Lock()
    async def increment_requests(self):
        async with self._lock:
            self.request_count += 1
    async def increment_errors(self):
        async with self._lock:
            self.error_count += 1
    def snapshot(self):
        # Safe to read without lock for logging
        return self.request_count, self.error_count


# ==================== SIMPLE LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== RESPONSE GENERATORS ====================
def generate_response(request: HTTPRequest, metrics: Metrics) -> bytes:
    """Generate HTTP response"""
    if request.path == "/metrics":
        reqs, errs = metrics.snapshot()
        body = f"requests_total {reqs}\n errors_total {errs}\n"
        return body.encode('utf-8')
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

async def proxy_to_upstream(
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        request: HTTPRequest,
        upstream_host: str = UPSTREAM_HOST,
        upstream_port: int = UPSTREAM_PORT
) -> None:
    """Forward HTTP Request to upstream and stream response back
    Args:
        client_reader: Connection reader from client (unused, kept for interface consistency)
        client_writer: Connection writer to client for sending response
        request: Parsed HTTPRequest object with method, path, headers, body
        upstream_host: Hostname/IP of upstream server (default: localhost)
        upstream_port: Port of upstream server (default: 3001)
        
    Raises:
        asyncio.TimeoutError: If connection to upstream times out (5s)
        
    Note:
        This function handles all I/O and cleanup. The caller should return
        immediately after calling this function."""
    upstream_reader = upstream_writer = None
    try:
        #Connect to upstream
        upstream_reader, upstream_writer = await asyncio.wait_for(asyncio.open_connection(upstream_host, upstream_port),
        timeout = 5.0
        )
        # Send Request line
        request_line = f"{request.method} {request.path} {request.version}\r\n"
        upstream_writer.write(request_line.encode())

        #Send Headers (fix Host Header)
        headers = request.headers.copy()
        headers["Host"] = f"{upstream_host}:{upstream_port}"
        for key, val in headers.items():
            upstream_writer.write(f"{key}: {val}\r\n".encode())
        upstream_writer.write(b"\r\n")

        #Send Body If Exists
        if request.body:
            upstream_writer.write(request.body)
        await upstream_writer.drain()

        #Stream response back to client
        while True:
            chunk = await upstream_reader.read(4096)
            if not chunk:
                break
            client_writer.write(chunk)
            await client_writer.drain()
    
    except asyncio.TimeoutError:
        if not client_writer.is_closing():
            client_writer.write(b"HTTP/1.1 504 Gateway Timeout\r\nContent-Length: 0\r\n\r\n")
            await client_writer.drain()
    except Exception as e:
        logger.error("Proxy error: %s", e)
        if not client_writer.is_closing():
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            await client_writer.drain()
    finally:
        if upstream_writer:
            upstream_writer.close()
            await upstream_writer.wait_closed()



# ==================== MAIN CLIENT HANDLER ====================
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, metrics: Metrics, semaphore: asyncio.Semaphore) -> None:
    """Handle client - never crashes, always cleans up"""
    
    async with semaphore:
        client_addr = writer.get_extra_info("peername")
        await metrics.increment_requests()
        start_time = time.time()
    
        # SAFETY: Initialize variables
        request = None
        method = "UNKNOWN"
        path = "UNKNOWN"
        
        total_reqs, _ = metrics.snapshot()
        logger.info("Client connected: %s (total: %d)", client_addr, total_reqs)
        
        try:
            # Parse request (can fail completely)
            logger.debug("Starting request parse for %s", client_addr)
            request = await parse_request_production(reader, client_addr)
            
            # Only set these if parsing succeeded
            method = request.method
            path = request.path
            
            # Proxy mode for /proxy/* paths
            if request.path.startswith(PROXY_PREFIX):
                new_path = request.path[len(PROXY_PREFIX):] 
                if not new_path or not new_path.startswith("/"):
                    new_path = "/" + new_path.lstrip("/")
                proxied_request = HTTPRequest(
                    method=request.method,
                    path=new_path,
                    version=request.version,
                    headers=request.headers,
                    body=request.body
                )
                await proxy_to_upstream(reader, writer, proxied_request)
                return #Proxy handles all I/O
            
            #ECHO mode
            response = generate_response(request, metrics)
            await send_response(writer, response)
            
            
            # Success metrics
            duration = time.time() - start_time
            logger.info("Request completed: %s %s (%.3fs)", method, path, duration)
            
        except ValueError as e:
            # Handle parsing errors gracefully
            await metrics.increment_errors()
            logger.warning("Bad request from %s: %s", client_addr, e)
            
            # Send proper error response
            error_msg = "BAD REQUEST"
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
            await metrics.increment_errors()
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
            await metrics.increment_errors()
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
            reqs, errs = metrics.snapshot()
            logger.info("Disconnecting %s (requests: %d, errors: %d)", 
                    client_addr, reqs, errs)
            writer.close()
            await writer.wait_closed()


# ==================== MAIN FUNCTION ====================
async def main():
    """Main function"""
    metrics = Metrics()    
    config = Config.from_env()
    semaphore = asyncio.Semaphore(config.max_connections)
    logger.info("Starting DevProxy server on %s:%d", config.host, config.port)
    reqs, errs = metrics.snapshot()
    logger.info("Initial metrics - requests: %d, errors: %d", reqs, errs)
    
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, metrics, semaphore),
        "127.0.0.1", 
        8889,
        reuse_address=True,
        backlog=128
    )
    
    addr = server.sockets[0].getsockname()
    logger.info("Server started on %s", addr)
    
    try:
        async with server:
            await server.serve_forever()
    except KeyboardInterrupt:
        final_reqs, final_errs = metrics.snapshot()
        logger.info("Server stopped by user (final: requests=%d, errors=%d)", final_reqs, final_errs)
    except Exception as e:
        logger.error("Server crashed: %s", e, exc_info=True)
        raise


# ==================== STARTUP ====================
if __name__ == "__main__":
    asyncio.run(main())