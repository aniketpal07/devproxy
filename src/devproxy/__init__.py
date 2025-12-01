"""
DevProxy - Production-grade HTTP infrastructure
"""

__version__ = "1.0.0"
__author__ = "Aniket"

# Public API
from .server import main as run_server

__all__ = ['run_server', '__version__']