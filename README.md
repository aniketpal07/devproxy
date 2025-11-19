# DevProxy

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
| **Requests/sec** | 2,588.15 |
| **Total requests** | 25,958 |
| **Average latency** | 38.6ms |
| **P95 latency** | 44.3ms |
| **P99 latency** | 51.9ms |
| **Success rate** | 100% |

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

# Run tests
pytest
```


## Acknowledgments

Built with ❤️ using pure Python - no external dependencies required.