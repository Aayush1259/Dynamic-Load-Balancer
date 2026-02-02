# Distributed Load Balancer

A production-ready distributed load balancer implementing the Least Connections algorithm with automated health monitoring and zero-downtime fault tolerance.

## Features

- **Intelligent Load Balancing** - Least Connections algorithm for optimal traffic distribution
- **Zero-Downtime Fault Tolerance** - Automatic failure detection and recovery within 5 seconds
- **Real-Time Monitoring** - Beautiful web dashboard with live metrics
- **Comprehensive Testing** - Stress testing, fault injection, and algorithm comparison
- **Professional Logging** - Structured logging to both file and console
- **Horizontal Scalability** - Easy worker addition via configuration

## Quick Start

### Installation

```bash
# Clone repository
git clone <your-repo-url>
cd distributed_lb

# Install dependencies
pip install -r requirements.txt
```

### Running the System

**Start Workers (3 separate terminals):**
```bash
python app/worker.py 5001
python app/worker.py 5002
python app/worker.py 5003
```

**Start Load Balancer:**
```bash
python app/balancer.py
```

### Access Points

- **Load Balancer:** http://127.0.0.1:8000
- **Dashboard:** http://127.0.0.1:8000/status
- **Metrics API:** http://127.0.0.1:8000/metrics

## Project Structure

```
distributed_lb/
├── app/
│   ├── balancer.py          # Load balancer with Least Connections algorithm
│   └── worker.py            # Backend worker nodes
├── tests/
│   ├── stress_test.py       # Performance testing (100-1000 concurrent requests)
│   ├── fault_injection.py   # Automated fault tolerance validation
│   └── algorithm_comparison.py  # LC vs RR comparison
├── config.yaml              # System configuration
├── requirements.txt         # Python dependencies
├── .gitignore              # Git exclusions
└── README.md               # This file
```

## Testing

### Stress Test
```bash
python tests/stress_test.py
```
Tests performance under various load levels (100-1000 requests).

### Fault Injection
```bash
python tests/fault_injection.py
```
Verifies zero-downtime during node failures. **Manually kill a worker when prompted.**

### Algorithm Comparison
```bash
python tests/algorithm_comparison.py
```
Compares Least Connections vs Round Robin with statistical analysis.

## Architecture

```
                        ┌─────────────────────┐
                        │   Client Requests   │
                        └──────────┬──────────┘
                                   │
                                   ▼
                   ┌────────────────────────────────┐
                   │   Load Balancer (Port 8000)    │
                   │  • Least Connections Algorithm │
                   │  • Health Monitoring (5s)      │
                   │  • Metrics Tracking            │
                   └─────────┬──────────────────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
         ┌──────────┐ ┌──────────┐ ┌──────────┐
         │ Worker 1 │ │ Worker 2 │ │ Worker 3 │
         │ Port 5001│ │ Port 5002│ │ Port 5003│
         └──────────┘ └──────────┘ └──────────┘
```

### Request Flow

1. Client sends request to load balancer (port 8000)
2. Balancer filters for healthy workers
3. Selects worker with fewest active connections
4. Proxies request to selected worker
5. Worker processes and returns response
6. Balancer forwards response to client

### Health Monitoring

- **Pull-based heartbeats** every 5 seconds
- **2-second timeout** for quick failure detection
- Automatic node exclusion when unhealthy
- Automatic re-inclusion upon recovery

## Configuration

Edit `config.yaml` to add/remove workers:

```yaml
servers:
  - url: http://127.0.0.1:5001
    name: worker-1
    weight: 1
  # Add more workers here
```

## Metrics & Monitoring

### Web Dashboard
Visit http://127.0.0.1:8000/status for real-time monitoring with:
- System uptime
- Total requests and success rate
- Average response time
- Per-worker status and statistics

### JSON API
GET http://127.0.0.1:8000/metrics for programmatic access to:
- Performance metrics
- Node health status
- Request distribution data

## Technical Details

### Algorithm: Least Connections

**Why Least Connections?**
- Adapts to variable request processing times
- Better load distribution than Round Robin
- Industry-standard (AWS ELB, Google Cloud LB)

**How it works:**
1. Track active connections per worker
2. Increment counter when routing
3. Decrement in `finally` block (guarantees accuracy)
4. Select worker with minimum count

### Fault Tolerance

**Zero-Downtime Guarantee:**
- Health monitor marks failed nodes as unhealthy
- Routing algorithm excludes unhealthy nodes
- All requests succeed unless ALL nodes fail
- Tested and verified via `fault_injection.py`

## Performance

Tested with stress_test.py:

| Load Level | Requests | Concurrent | Success Rate | Avg Response |
|------------|----------|------------|--------------|--------------|
| Light      | 100      | 10         | 100%         | ~3ms         |
| Medium     | 500      | 50         | 100%         | ~5ms         |
| Heavy      | 1000     | 100        | 100%         | ~8ms         |

## Logs

Logs are written to:
- `logs/load_balancer.log` - Load balancer activity
- `logs/worker_5001.log` - Worker 1 activity
- `logs/worker_5002.log` - Worker 2 activity
- `logs/worker_5003.log` - Worker 3 activity

## Dependencies

```
Flask==3.0.0
requests==2.31.0
aiohttp==3.9.1
pyyaml==6.0.1
```

## Use Cases

**Development:**
- Microservices architecture
- API gateway simulation
- Distributed systems learning

**Production Concepts:**
- Horizontal scaling patterns
- Health monitoring strategies
- Fault-tolerant design

## Real-World Comparison

| Feature | This Project | AWS ELB | Google Cloud LB |
|---------|--------------|---------|-----------------|
| Algorithm | Least Connections | Least Connections | Least Connections |
| Health Checks | 5s interval | 30s interval | 5-60s interval |
| Fault Detection | ~5s | ~30s | ~10s |
| Zero Downtime | ✓ | ✓ | ✓ |
| Scale | 3-10 nodes | Millions | Millions |

## Limitations

- Load balancer is single point of failure (would need multiple LBs in production)
- No session persistence (cookies/sticky sessions)
- HTTP only (no HTTPS)
- Local network only (no geographic distribution)

## Future Enhancements

- [ ] Weighted load balancing
- [ ] Session affinity
- [ ] SSL/TLS support
- [ ] Multiple load balancer instances with DNS failover
- [ ] Dynamic worker discovery (service registry)
- [ ] Circuit breaker pattern
- [ ] Request rate limiting

## License

MIT License - feel free to use for learning and projects.

## Author

Aayush Modi  
TCSS 558 - Applied Distributed Computing  
University of Washington Tacoma

## Acknowledgments

- Course concepts from TCSS 558 Topic 1.2 (Container Network Parallelization)
- Algorithm inspired by AWS Elastic Load Balancing
- Health monitoring patterns from production distributed systems
