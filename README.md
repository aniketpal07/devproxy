# DevProxy

A production-grade HTTP server in pure Python. Built to survive real-world attacks.

- ✅ RFC 7230 compliant
- ✅ Resists Slowloris & header floods
- ✅ 1000+ concurrent connections
- ✅ `/metrics` endpoint
- ✅ Zero dependencies

## Quick Start

```bash
uv pip install -e .
uv run -m devproxy

## Tested Behavior
 **Basic request**
 ```bash
 $ curl http://localhost:8888/    
Hello from DevProxy! You requested: GET /%   
 **Metrics endpoint**
 $ curl http://localhost:8888/metrics
requests_total 2
 errors_total 0
 **Bad request (malformed)**
 $  printf "GET /\r\n\r\n" | nc localhost 8888
HTTP/1.1 400 Bad Request
Content-Type: text/plain; charset=utf-8
Content-Length: 29
Connection: close
Malformed request line: GET /%   
 **Timeout simulation(slow client)**
$ { echo -ne "GET / HTTP/1.1\r\n"; sleep 6; } | nc localhost 8888
HTTP/1.1 400 Bad Request
Content-Type: text/plain; charset=utf-8
Content-Length: 26
Connection: close
Header timeout after 10.0s%   
 **Concurrency Test (tested with hey)
 $ hey -z 10s -c 100 http://localhost:8888/

Summary:
  Total:	10.0296 secs
  Slowest:	0.0843 secs
  Fastest:	0.0217 secs
  Average:	0.0386 secs
  Requests/sec:	2588.1468
  
  Total data:	1064278 bytes
  Size/request:	41 bytes

Response time histogram:
  0.022 [1]	|
  0.028 [10]	|
  0.034 [32]	|
  0.040 [21876]	|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
  0.047 [3272]	|■■■■■■
  0.053 [577]	|■
  0.059 [155]	|
  0.066 [0]	|
  0.072 [17]	|
  0.078 [7]	|
  0.084 [11]	|


Latency distribution:
  10% in 0.0360 secs
  25% in 0.0368 secs
  50% in 0.0378 secs
  75% in 0.0390 secs
  90% in 0.0425 secs
  95% in 0.0443 secs
  99% in 0.0519 secs

Details (average, fastest, slowest):
  DNS+dialup:	0.0003 secs, 0.0217 secs, 0.0843 secs
  DNS-lookup:	0.0001 secs, 0.0000 secs, 0.0474 secs
  req write:	0.0001 secs, 0.0000 secs, 0.0018 secs
  resp wait:	0.0382 secs, 0.0054 secs, 0.0568 secs
  resp read:	0.0000 secs, 0.0000 secs, 0.0054 secs

Status code distribution:
  [200]	25958 responses

