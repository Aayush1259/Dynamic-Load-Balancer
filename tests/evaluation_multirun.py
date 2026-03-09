import argparse
import concurrent.futures
import random
import statistics
import time
from typing import Dict, List, Tuple

import requests


def send_request(url: str, timeout: float = 5.0) -> Tuple[bool, float]:
    start = time.time()
    try:
        resp = requests.get(url, timeout=timeout)
        elapsed = time.time() - start
        return resp.status_code == 200, elapsed
    except Exception:
        elapsed = time.time() - start
        return False, elapsed


def run_stress_once(url: str, requests_n: int, concurrency: int, timeout: float = 5.0) -> Dict[str, float]:
    durations: List[float] = []
    ok = 0
    fail = 0

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(send_request, url, timeout) for _ in range(requests_n)]
        for fut in concurrent.futures.as_completed(futures):
            success, elapsed = fut.result()
            if success:
                ok += 1
                durations.append(elapsed)
            else:
                fail += 1

    total = time.time() - start
    throughput = ok / total if total > 0 else 0.0
    avg_ms = (statistics.mean(durations) * 1000.0) if durations else 0.0
    p95_ms = (statistics.quantiles(durations, n=20)[18] * 1000.0) if len(durations) >= 20 else 0.0
    success_rate = (ok / requests_n) * 100.0 if requests_n > 0 else 0.0

    return {
        "requests": requests_n,
        "concurrency": concurrency,
        "ok": ok,
        "fail": fail,
        "total_s": total,
        "throughput": throughput,
        "avg_ms": avg_ms,
        "p95_ms": p95_ms,
        "success_rate": success_rate,
    }


def summarize_stress(url: str, scenarios: List[Tuple[int, int]], repeats: int) -> Dict[Tuple[int, int], Dict[str, float]]:
    out: Dict[Tuple[int, int], Dict[str, float]] = {}

    for req_n, conc in scenarios:
        runs: List[Dict[str, float]] = []
        for _ in range(repeats):
            runs.append(run_stress_once(url, req_n, conc))

        def m(key: str) -> float:
            return statistics.mean(r[key] for r in runs)

        def s(key: str) -> float:
            return statistics.stdev(r[key] for r in runs) if repeats > 1 else 0.0

        out[(req_n, conc)] = {
            "repeats": repeats,
            "ok_mean": m("ok"),
            "fail_mean": m("fail"),
            "success_rate_mean": m("success_rate"),
            "throughput_mean": m("throughput"),
            "throughput_std": s("throughput"),
            "avg_ms_mean": m("avg_ms"),
            "avg_ms_std": s("avg_ms"),
            "p95_ms_mean": m("p95_ms"),
            "p95_ms_std": s("p95_ms"),
        }

    return out


def simulate_rr_lc_once(total_requests: int, seed: int) -> Dict[str, float]:
    random.seed(seed)
    servers = ["S1", "S2", "S3"]

    rr = {s: 0 for s in servers}
    for i in range(total_requests):
        rr[servers[i % len(servers)]] += 1

    lc = {s: 0 for s in servers}
    current = {s: 0 for s in servers}
    for i in range(total_requests):
        target = min(current, key=current.get)
        lc[target] += 1
        current[target] += 1
        if i % 3 == 0:
            freed = random.choice(servers)
            if current[freed] > 0:
                current[freed] -= 1

    return {
        "rr_var": statistics.variance(rr.values()),
        "lc_var": statistics.variance(lc.values()),
        "rr_s1": rr["S1"],
        "rr_s2": rr["S2"],
        "rr_s3": rr["S3"],
        "lc_s1": lc["S1"],
        "lc_s2": lc["S2"],
        "lc_s3": lc["S3"],
    }


def summarize_algo(total_requests: int, seeds: List[int]) -> Dict[str, float]:
    rows = [simulate_rr_lc_once(total_requests, seed) for seed in seeds]

    def m(key: str) -> float:
        return statistics.mean(r[key] for r in rows)

    def s(key: str) -> float:
        return statistics.stdev(r[key] for r in rows) if len(rows) > 1 else 0.0

    return {
        "runs": len(seeds),
        "rr_var_mean": m("rr_var"),
        "rr_var_std": s("rr_var"),
        "lc_var_mean": m("lc_var"),
        "lc_var_std": s("lc_var"),
        "rr_s1_mean": m("rr_s1"),
        "rr_s2_mean": m("rr_s2"),
        "rr_s3_mean": m("rr_s3"),
        "lc_s1_mean": m("lc_s1"),
        "lc_s2_mean": m("lc_s2"),
        "lc_s3_mean": m("lc_s3"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Repeated evaluation harness for load balancer report metrics")
    parser.add_argument("--url", default="http://127.0.0.1:8000/", help="Balancer URL")
    parser.add_argument("--repeats", type=int, default=3, help="Stress repeats per workload")
    parser.add_argument("--algo-runs", type=int, default=20, help="Algorithm comparison repeated runs via seeds 1..N")
    args = parser.parse_args()

    scenarios = [(200, 20), (500, 50), (1000, 100)]
    stress = summarize_stress(args.url, scenarios, args.repeats)
    algo = summarize_algo(100, list(range(1, args.algo_runs + 1)))

    print("=" * 72)
    print("STRESS MULTI-RUN SUMMARY")
    print("=" * 72)
    print("Req/Conc | repeats | succ% | thrpt_mean +/- std | avg_ms_mean +/- std | p95_ms_mean +/- std")
    for req_n, conc in scenarios:
        row = stress[(req_n, conc)]
        print(
            f"{req_n:>4}/{conc:<3} | {int(row['repeats']):>7} | "
            f"{row['success_rate_mean']:>5.1f} | "
            f"{row['throughput_mean']:>8.2f} +/- {row['throughput_std']:<6.2f} | "
            f"{row['avg_ms_mean']:>9.2f} +/- {row['avg_ms_std']:<7.2f} | "
            f"{row['p95_ms_mean']:>10.2f} +/- {row['p95_ms_std']:<7.2f}"
        )

    print("\n" + "=" * 72)
    print("ALGORITHM MULTI-RUN SUMMARY (RR vs LC simulation)")
    print("=" * 72)
    print(f"runs (seeds): {algo['runs']}")
    print(
        f"RR variance mean +/- std: {algo['rr_var_mean']:.2f} +/- {algo['rr_var_std']:.2f}\n"
        f"LC variance mean +/- std: {algo['lc_var_mean']:.2f} +/- {algo['lc_var_std']:.2f}"
    )
    print(
        f"RR mean counts: S1={algo['rr_s1_mean']:.2f}, S2={algo['rr_s2_mean']:.2f}, S3={algo['rr_s3_mean']:.2f}\n"
        f"LC mean counts: S1={algo['lc_s1_mean']:.2f}, S2={algo['lc_s2_mean']:.2f}, S3={algo['lc_s3_mean']:.2f}"
    )


if __name__ == "__main__":
    main()
