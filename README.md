# Dynamic Distributed Load Balancer

**Course:** TCSS 558 — Applied Distributed Computing  
**Term:** Winter 2026  
**Institution:** University of Washington Tacoma  
**Author:** Aayush Kiratbhai Modi (`aayush18@uw.edu`)

---

## Project Overview

This project implements a self-healing distributed load balancer in Python
using the Master-Worker (SPMD) architecture. The system routes client HTTP
requests across a pool of stateless backend workers using the **Least
Connections** algorithm, which selects the healthy worker with the fewest
active connections weighted by capacity. A background **heartbeat monitor**
daemon thread detects worker failures within 5 seconds and excludes them from
routing, enabling zero-downtime behavior during live worker terminations.

### Key Features

- **Least Connections routing** — adaptive, weighted selection based on live
  in-flight connection counts (`active_connections / weight`)
- **Heartbeat-based health monitoring** — asynchronous daemon thread pings
  workers every 5 s with a 2 s timeout
- **Reactive + proactive fault handling** — connection errors immediately mark
  a node unhealthy; the heartbeat confirms and detects silent failures
- **Thread-safe shared state** — `threading.Lock` protects server registry and
  metrics counters; `try-finally` guarantees counter rollback
- **Observable runtime state** — HTML dashboard (`/status`) and JSON API
  (`/metrics`)
- **Configuration-driven** — YAML file controls worker membership, weights,
  heartbeat parameters, and balancer port with zero code changes

### Distributed Systems Concepts Demonstrated

| Concept | Implementation |
|---|---|
| SPMD Paradigm | Master-Worker architecture from a single codebase |
| Load Balancing | Weighted Least Connections algorithm |
| Failure Detection | Pull-based heartbeat protocol |
| Latency Hiding | Daemon thread decouples monitoring from request handling |
| Mutual Exclusion | `threading.Lock` for shared mutable state |
| Thread Safety | `try-finally` pattern for counter correctness |
| Data Decomposition | YAML config for horizontal scaling |

---

## Repository Structure

```
Dynamic-Load-Balancer/
├── app/
│   ├── __init__.py              # Package metadata
│   ├── balancer.py              # Master: LC router, health monitor, dashboard
│   └── worker.py                # Worker: request handler, /health endpoint
├── tests/
│   ├── stress_test.py           # Multi-threaded throughput/latency benchmark
│   ├── algorithm_comparison.py  # RR vs LC simulation (seeded)
│   ├── fault_injection.py       # Manual fault-injection probe
│   ├── evaluation_multirun.py   # Repeated-run stress + algo aggregation
│   ├── extreme_evaluation.py    # Hidden-workload LC evaluation
│   └── fault_multirun.py        # Automated multi-trial fault injection
├── logs/                        # Runtime logs (gitignored, auto-created)
├── config.yaml                  # System configuration
├── requirements.txt             # Python dependencies
└── README.md
```

---

## Prerequisites

- **Python 3.10+** (tested with Python 3.12)
- **pip** (comes with Python)
- Terminal access (PowerShell on Windows, or bash/zsh on macOS/Linux)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Aayush1259/Dynamic-Load-Balancer.git
cd Dynamic-Load-Balancer
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs: `flask`, `requests`, `pyyaml`.

---

## How to Run

You need **4 separate terminals**, all in the project root with the virtual
environment activated.

### Step 1 — Start Workers (3 terminals)

```bash
# Terminal 1
python app/worker.py 5001

# Terminal 2
python app/worker.py 5002

# Terminal 3
python app/worker.py 5003
```

### Step 2 — Start the Load Balancer (1 terminal)

```bash
# Terminal 4
python app/balancer.py
```

### Step 3 — Verify the system

Open these URLs in a browser:

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/` | Send a test request (should show which worker handled it) |
| `http://127.0.0.1:8000/status` | Live HTML dashboard with worker health and metrics |
| `http://127.0.0.1:8000/metrics` | JSON API with throughput, latency, and per-node stats |

---

## Configuration

All runtime parameters are in `config.yaml`:

```yaml
servers:
  - url: http://127.0.0.1:5001
    name: worker-1
    weight: 1
  - url: http://127.0.0.1:5002
    name: worker-2
    weight: 1
  - url: http://127.0.0.1:5003
    name: worker-3
    weight: 1
health_check:
  interval_seconds: 5
  timeout_seconds: 2
load_balancer:
  port: 8000
  algorithm: least_connections
  log_level: INFO
```

- **Add a worker:** add a new `url` entry under `servers` and start the
  process on that port
- **Change weights:** set `weight` per server for capacity-proportional routing
- **Tune heartbeat:** adjust `interval_seconds` and `timeout_seconds`

---

## Running the Evaluation Tests

All tests require the core system (3 workers + balancer) to be running first.

### A. Stress Test — throughput and latency under load

```bash
python tests/stress_test.py --requests 500 --concurrency 50
```

Sends 500 concurrent requests and reports success rate, throughput (req/s),
mean latency, and P95 latency.

### B. Algorithm Comparison — RR vs LC simulation

```bash
python tests/algorithm_comparison.py --requests 100 --seed 42
```

Simulates Round-Robin and Least Connections on 3 servers with randomized
connection releases. Reports per-server assignment counts and variance.

### C. Fault Injection — zero-downtime validation

```bash
python tests/fault_injection.py --interval 0.5 --timeout 2.0
```

Continuously probes the balancer. While running, **kill one worker** (e.g.,
Ctrl+C on the Worker-5002 terminal) and observe that requests continue
succeeding through the remaining healthy workers.

### D. Multi-Run Aggregate Evaluation

```bash
python tests/evaluation_multirun.py --repeats 3 --algo-runs 20
```

Runs stress tests at 3 operating points (200/20, 500/50, 1000/100) with 3
repeats each, plus 20 seeded algorithm-comparison runs. Outputs mean ± std
tables for aggregate analysis.

### E. Extreme Hidden-Workload Evaluation (LC only)

```bash
python tests/extreme_evaluation.py --repeats 3 --timeout 3.0 --seed 558
```

Tests LC under 5 hidden-cost scenarios (uniform, bimodal, heavy-tail, bursty)
where per-request processing cost is unknown to the balancer at routing time.

### F. Automated Fault Multi-Run

```bash
python tests/fault_multirun.py --trials 3 --requests 120 --kill-at 40
```

Spawns isolated worker/balancer processes, automatically kills Worker-2 at
request 40, measures pre/post success rates and recovery time across trials.

---

## Logs

Runtime logs are written to the `logs/` directory (auto-created on startup):

| File | Contents |
|---|---|
| `logs/load_balancer.log` | Master routing decisions, health state changes |
| `logs/worker_5001.log` | Worker-1 request and health-check activity |
| `logs/worker_5002.log` | Worker-2 activity |
| `logs/worker_5003.log` | Worker-3 activity |

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `Address already in use` | Kill existing processes on those ports, or restart terminals |
| `ModuleNotFoundError: flask` | Activate the virtual environment and run `pip install -r requirements.txt` |
| `Configuration Error` | Ensure `config.yaml` exists in the working directory |
| Workers show `UNHEALTHY` on dashboard | Verify worker processes are running on the correct ports |
- `ModuleNotFoundError`: activate venv and reinstall requirements.
- Worker shutdown signal issue on Windows: already handled in code with
	portable `SIGTERM` fallback.
