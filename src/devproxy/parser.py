import asyncio
import logging
from typing import Dict
from dataclasses import dataclass

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


