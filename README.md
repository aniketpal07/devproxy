# DevProxy

[![Tests](https://github.com/aniketpal07/devproxy/actions/workflows/tests.yml/badge.svg)](https://github.com/aniketpal07/devproxy/actions/workflows/tests.yml)
[![Tests](https://github.com/aniketpal07/devproxy/actions/workflows/tests.yml/badge.svg)](https://github.com/aniketpal07/devproxy/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A production-grade HTTP server in pure Python. Built to survive real-world attacks.

## Features

- ✅ **RFC 7230 compliant** - Follows HTTP/1.1 specification
- ✅ **Attack-resistant** - Withstands Slowloris & header floods
- ✅ **High concurrency** - Handles 1000+ simultaneous connections
- ✅ **Built-in monitoring** - `/metrics` endpoint for observability
- ✅ **Zero dependencies** - Pure Python implementation

## Quick Start

```bash
# Install the package
uv pip install -e .

# Run the server
uv run -m devproxy
```

The server will start on `http://localhost:8888`

## Usage Examples

### Basic Request

```bash
$ curl http://localhost:8888/
Hello from DevProxy! You requested: GET /
```

### Metrics Endpoint

Monitor server health and performance:

```bash
$ curl http://localhost:8888/metrics
requests_total 2
errors_total 0
```

### Error Handling

**Malformed Request:**
```bash
$ printf "GET /\r\n\r\n" | nc localhost 8888
HTTP/1.1 400 Bad Request
Content-Type: text/plain; charset=utf-8
Content-Length: 29
Connection: close

Malformed request line: GET /
```

**Timeout Protection:**
```bash
$ { echo -ne "GET / HTTP/1.1\r\n"; sleep 6; } | nc localhost 8888
HTTP/1.1 400 Bad Request
Content-Type: text/plain; charset=utf-8
Content-Length: 26
Connection: close

Header timeout after 10.0s
```

## Performance Benchmarks

Tested with [hey](https://github.com/rakyll/hey) - a modern load testing tool:

```bash
$ hey -z 10s -c 100 http://localhost:8888/
```

### Results

| Metric | Value |
|--------|-------|
| **Requests/sec** | 2,527.06 |
| **Total requests** | 25,367 |
| **Success rate** | 100% |
| **Average latency** | 39.5ms |
| **P95 latency** | 50.9ms |
| **P99 latency** | 71.9ms |
| **Errors** | 3 / 25,374 (99.98% success) |

#### Response Time Distribution

```
  0.022s [1]     |
  0.028s [10]    |
  0.034s [32]    |
  0.040s [21876] |████████████████████████████████████████
  0.047s [3272]  |██████
  0.053s [577]   |█
  0.059s [155]   |
  0.084s [28]    |
```

#### Latency Percentiles

- **P50**: 37.8ms
- **P75**: 39.0ms
- **P90**: 42.5ms
- **P95**: 44.3ms
- **P99**: 51.9ms

## Security Features

- **Slowloris Protection** - Request timeout enforcement
- **Header Flood Mitigation** - Limited header processing
- **Connection Limits** - Prevents resource exhaustion
- **Input Validation** - Strict HTTP parsing

## Development

### Requirements

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager

### Running Tests

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run all tests
pytest -v

# Run with coverage report
pytest --cov=devproxy --cov-report=term-missing

# Run specific test file
pytest tests/test_parser.py -v
pytest tests/test_proxy.py -v
```

### Manual Testing

```bash
# Terminal 1: Start DevProxy
uv run -m devproxy

# Terminal 2: Start upstream server (for proxy testing)
python3 -m http.server 3001

# Terminal 3: Test endpoints
curl http://localhost:8889/                    # Echo endpoint
curl http://localhost:8889/metrics             # Metrics
curl http://localhost:8889/proxy/              # Proxy to upstream
```

### Configuration

DevProxy can be configured via environment variables:

```bash
# Server settings
export DEVPROXY_HOST="0.0.0.0"      # Default: 127.0.0.1
export DEVPROXY_PORT="8080"          # Default: 8889

# Upstream settings
export UPSTREAM_HOST="api.example.com"  # Default: localhost
export UPSTREAM_PORT="8000"             # Default: 3001

# Performance tuning
export MAX_CONNECTIONS="2000"        # Default: 1000

# Run with custom config
uv run -m devproxy
```

## License
MIT License - see LICENSE file for details

## Acknowledgments
Built with ❤️ using pure Python - no external dependencies required.

