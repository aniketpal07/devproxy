import asyncio
import pytest
from devproxy.parser import parse_request_production, HTTPRequest

@pytest.mark.asyncio
async def test_valid_http_request():
    """Test parsing a valid HTTP/1.1 request"""
    request_data = b"GET /test HTTP/1.1\r\nHost: localhost\r\nUser-Agent: test\r\n\r\n"
    reader = asyncio.StreamReader()
    reader.feed_data(request_data)
    reader.feed_eof()

    request = await parse_request_production(reader, ("127.0.0.1", 12345))

    assert isinstance(request, HTTPRequest)
    assert request.method == "GET"
    assert request.path == "/test"
    assert request.version == "HTTP/1.1"
    assert request.headers["Host"] == "localhost"
    assert request.body == b""

if __name__ == "__main__":
    asyncio.run(test_valid_http_request())
    