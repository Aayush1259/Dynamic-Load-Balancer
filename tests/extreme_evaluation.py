import argparse
import concurrent.futures
import random
import statistics
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import requests


@dataclass
class Scenario:
    name: str
    requests_n: int
    concurrency: int
    workload_sampler: Callable[[], float]


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * p
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    return values_sorted[f] + (values_sorted[c] - values_sorted[f]) * (k - f)


def send_one(url: str, work_ms: float, timeout: float) -> Tuple[bool, float]:
    start = time.time()
    try:
        r = requests.get(url, params={"work_ms": f"{work_ms:.2f}"}, timeout=timeout)
        elapsed = (time.time() - start) * 1000.0
        return r.status_code == 200, elapsed
    except Exception:
        elapsed = (time.time() - start) * 1000.0
        return False, elapsed


def metrics_snapshot(metrics_url: str) -> Dict:
    r = requests.get(metrics_url, timeout=3)
    r.raise_for_status()
    return r.json()


def node_counts(snapshot: Dict) -> Dict[str, int]:
    return {node["name"]: int(node.get("total_requests", 0)) for node in snapshot.get("nodes", [])}


def run_scenario_once(base_url: str, metrics_url: str, scenario: Scenario, timeout: float) -> Dict[str, float]:
    before = metrics_snapshot(metrics_url)
    before_counts = node_counts(before)

    latencies: List[float] = []
    success = 0
    fail = 0

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=scenario.concurrency) as ex:
        futures = [
            ex.submit(send_one, base_url, scenario.workload_sampler(), timeout)
            for _ in range(scenario.requests_n)
        ]
        for fut in concurrent.futures.as_completed(futures):
            ok, lat_ms = fut.result()
            if ok:
                success += 1
                latencies.append(lat_ms)
            else:
                fail += 1

    total_s = time.time() - start

    after = metrics_snapshot(metrics_url)
    after_counts = node_counts(after)

    names = sorted(set(before_counts) | set(after_counts))
    deltas = [max(0, after_counts.get(n, 0) - before_counts.get(n, 0)) for n in names]
    assign_var = statistics.pvariance(deltas) if len(deltas) > 1 else 0.0

    success_rate = 100.0 * success / scenario.requests_n if scenario.requests_n > 0 else 0.0
    throughput = success / total_s if total_s > 0 else 0.0
    avg_ms = statistics.mean(latencies) if latencies else 0.0
    p95_ms = percentile(latencies, 0.95)
    p99_ms = percentile(latencies, 0.99)

    return {
        "success_rate": success_rate,
        "throughput": throughput,
        "avg_ms": avg_ms,
        "p95_ms": p95_ms,
        "p99_ms": p99_ms,
        "assign_var": assign_var,
    }


def aggregate(rows: List[Dict[str, float]]) -> Dict[str, float]:
    def m(k: str) -> float:
        return statistics.mean(r[k] for r in rows)

    def s(k: str) -> float:
        return statistics.stdev(r[k] for r in rows) if len(rows) > 1 else 0.0

    return {
        "runs": len(rows),
        "success_rate_mean": m("success_rate"),
        "success_rate_std": s("success_rate"),
        "throughput_mean": m("throughput"),
        "throughput_std": s("throughput"),
        "avg_ms_mean": m("avg_ms"),
        "avg_ms_std": s("avg_ms"),
        "p95_ms_mean": m("p95_ms"),
        "p95_ms_std": s("p95_ms"),
        "p99_ms_mean": m("p99_ms"),
        "p99_ms_std": s("p99_ms"),
        "assign_var_mean": m("assign_var"),
        "assign_var_std": s("assign_var"),
    }


def build_scenarios() -> List[Scenario]:
    return [
        Scenario(
            name="uniform_10ms",
            requests_n=300,
            concurrency=30,
            workload_sampler=lambda: 10.0,
        ),
        Scenario(
            name="uniform_80ms",
            requests_n=300,
            concurrency=30,
            workload_sampler=lambda: 80.0,
        ),
        Scenario(
            name="bimodal_hidden_10_200",
            requests_n=600,
            concurrency=60,
            workload_sampler=lambda: 10.0 if random.random() < 0.75 else 200.0,
        ),
        Scenario(
            name="heavy_tail_hidden",
            requests_n=600,
            concurrency=60,
            workload_sampler=lambda: min(400.0, max(5.0, random.paretovariate(2.2) * 30.0)),
        ),
        Scenario(
            name="burst_hidden_phases",
            requests_n=800,
            concurrency=80,
            workload_sampler=lambda: 20.0 if random.random() < 0.6 else 250.0,
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extreme repeated evaluation harness with hidden workload scenarios")
    parser.add_argument("--url", default="http://127.0.0.1:8000/", help="Balancer URL")
    parser.add_argument("--metrics-url", default="http://127.0.0.1:8000/metrics", help="Metrics endpoint URL")
    parser.add_argument("--repeats", type=int, default=3, help="Repeats per scenario")
    parser.add_argument("--timeout", type=float, default=3.0, help="Per-request timeout seconds")
    parser.add_argument("--seed", type=int, default=558, help="RNG seed")
    args = parser.parse_args()

    random.seed(args.seed)
    scenarios = build_scenarios()

    print("=" * 96)
    print("EXTREME EVALUATION SUMMARY (LC, hidden workloads)")
    print("=" * 96)
    print("scenario | runs | succ% mean±std | thrpt mean±std | avg ms mean±std | p95 mean±std | p99 mean±std | assign-var mean±std")

    for sc in scenarios:
        rows = [run_scenario_once(args.url, args.metrics_url, sc, args.timeout) for _ in range(args.repeats)]
        a = aggregate(rows)
        print(
            f"{sc.name} | {a['runs']} | "
            f"{a['success_rate_mean']:.2f}±{a['success_rate_std']:.2f} | "
            f"{a['throughput_mean']:.2f}±{a['throughput_std']:.2f} | "
            f"{a['avg_ms_mean']:.2f}±{a['avg_ms_std']:.2f} | "
            f"{a['p95_ms_mean']:.2f}±{a['p95_ms_std']:.2f} | "
            f"{a['p99_ms_mean']:.2f}±{a['p99_ms_std']:.2f} | "
            f"{a['assign_var_mean']:.2f}±{a['assign_var_std']:.2f}"
        )


if __name__ == "__main__":
    main()
