import pytest
from devproxy.server import PROXY_PREFIX

def strip_proxy_prefix(path: str) -> str:
    """Helper function to test path stripping logic"""
    if not path.startswith(PROXY_PREFIX):
        return path
    new_path = path[len(PROXY_PREFIX):]
    if not new_path or not new_path.startswith("/"):
        new_path = "/" + new_path.lstrip("/")
    return new_path

def test_proxy_path_stripping():
    """Test various proxy path scenarios"""
    assert strip_proxy_prefix("/proxy/") == "/"
    assert strip_proxy_prefix("/proxy/test") == "/test"
    assert strip_proxy_prefix("/proxy") == "/"
    assert strip_proxy_prefix("/proxy/api/users") == "/api/users"
    assert strip_proxy_prefix("/health") == "/health"

