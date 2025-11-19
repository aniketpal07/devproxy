# Line 1: Package docstring
"""
DevProxy - Production-grade HTTP infrastructure
"""

# Line 4: Version info (for PyPI packages)
__version__ = "1.0.0"
__author__ = "Aniket"

# Line 7: Import main components
from .server import (
    HTTPRequest,           # Makes HTTPRequest available as devproxy.HTTPRequest
    HTTPLimits,           # Makes limits available as devproxy.HTTPLimits
    parse_request_production,  # Parser function
    handle_client,        # Main handler function
    main as run_server    # Alias main() to run_server()
)

# Line 16: Export list (tells Python what's public)
__all__ = [
    'HTTPRequest',
    'HTTPLimits',
    'parse_request_production', 
    'handle_client',
    'run_server',
    '__version__'
]