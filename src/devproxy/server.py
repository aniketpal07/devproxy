import asyncio
import time
from typing import Dict
from dataclasses import dataclass
import logging
from .parser import parse_request_production, HTTPRequest

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
        reqs, errs = metrics.sanpshot()
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
        
        logger.info("Client connected: %s (total: %d)", client_addr,)
        
        try:
            # Parse request (can fail completely)
            logger.debug("Starting request parse for %s", client_addr)
            request = await parse_request_production(reader, client_addr)
            
            # Only set these if parsing succeeded
            method = request.method
            path = request.path
            
            # Generate and send response
            logger.debug("Generating response for %s %s", method, path)
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
            logger.info("Timeout response sent to %s", client_addr,)
            
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
    semaphore = asyncio.Semaphore(1000)
    logger.info("Starting DevProxy server on port 8888")
    reqs, errs = metrics.snapshot()
    logger.info("Initial metrics - requests: %d, errors: %d", reqs, errs)
    
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, metrics, semaphore),
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
        logger.info("Server stopped by user (final: requests=%d, errors=%d)", reqs, errs)
    except Exception as e:
        logger.error("Server crashed: %s", e, exc_info=True)
        raise


# ==================== STARTUP ====================
if __name__ == "__main__":
    asyncio.run(main())