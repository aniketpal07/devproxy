import os
from dataclasses import dataclass

@dataclass
class Config:
    """Server Configuration"""
    host: str = "127.0.0.1"
    port: int = 8889
    upstream_host: str = "localhost"
    upstream_port: int = 3001
    max_connections: int = 1000

    @classmethod
    def from_env(cls):
        """Load Config from environment variables"""
        return cls(
            host = os.getenv("DEVPROXY_HOST", "127.0.0.1"),
            port = int(os.getenv("DEVPROXY_PORT", "8889")),
            upstream_host = os.getenv("UPSTREAM_HOST", "localhost"),
            upstream_port = int(os.getenv("UPSTREAM_PORT", "3001")),
            max_connections = int(os.getenv("MAX_CONNECTIONS", "1000"))
        )