import asyncio
import subprocess
import sys
import time
import socket
import pytest

async def wait_for_port(port: int, host: str = "127.0.0.1", timeout: int = 10):
    """Wait untill a port is open"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            await asyncio.sleep(0.2)
    return False

@pytest.mark.asyncio
async def test_proxy_intergration():
    """Test end-to-end proxy functionality"""
    # Start dummy upstream server
    upstream = subprocess.Popen([
        sys.executable, "-m", "http.server", "3001", "--bind", "127.0.0.1"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    #Start Devproxy
    proxy = subprocess.Popen([
        sys.executable, "-m", "devproxy"
    ], stdout=None, stderr=None)

    try:
        # Wait for servers
        assert await wait_for_port(3001, timeout=20), "Upstream server failed to start"
        assert await wait_for_port(8889, timeout=20), "DevProxy failed to start"
            
        # Test proxy endpoint
        reader, writer = await asyncio.open_connection("127.0.0.1", 8889)
        writer.write(b"GET /proxy/ HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
            
        response = await reader.read(1000)
        writer.close()
        await writer.wait_closed()
            
        assert b"200 OK" in response
        assert b"Directory listing" in response  # From http.server
            
        # Test echo endpoint
        reader, writer = await asyncio.open_connection("127.0.0.1", 8889)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
            
        response = await reader.read(1000)
        writer.close()
        await writer.wait_closed()
            
        assert b"Hello from DevProxy" in response
            
        print("All integration tests passed!")
            
    finally:
        proxy.terminate()
        upstream.terminate()
        proxy.wait()
        upstream.wait()

