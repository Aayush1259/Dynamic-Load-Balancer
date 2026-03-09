import argparse
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List

import requests


def wait_for_http(url: str, timeout_s: float = 20.0) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            r = requests.get(url, timeout=0.5)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for service: {url}")


def write_temp_config(cfg_path: Path, ports: List[int], balancer_port: int) -> None:
    content = f"""servers:
  - url: http://127.0.0.1:{ports[0]}
    name: worker-1
    weight: 1
  - url: http://127.0.0.1:{ports[1]}
    name: worker-2
    weight: 1
  - url: http://127.0.0.1:{ports[2]}
    name: worker-3
    weight: 1
health_check:
  interval_seconds: 1
  timeout_seconds: 0.5
load_balancer:
  port: {balancer_port}
  algorithm: least_connections
  log_level: WARNING
"""
    cfg_path.write_text(content, encoding="utf-8")


def one_trial(base_url: str, w2_proc: subprocess.Popen, python_exe: str, repo_root: Path, w2_port: int, requests_n: int, kill_at: int, interval_s: float) -> Dict[str, float]:
    events = []
    kill_time = None

    for i in range(requests_n):
        if i == kill_at:
            kill_time = time.time()
            try:
                w2_proc.terminate()
                w2_proc.wait(timeout=2)
            except Exception:
                try:
                    w2_proc.kill()
                except Exception:
                    pass

        t0 = time.time()
        ok = False
        try:
            r = requests.get(base_url, timeout=2.0)
            ok = (r.status_code == 200)
        except Exception:
            ok = False
        dt_ms = (time.time() - t0) * 1000.0
        events.append((time.time(), ok, dt_ms, i))
        time.sleep(interval_s)

    pre = events[:kill_at]
    post = events[kill_at:]

    def success_rate(rows):
        return 100.0 * sum(1 for _, ok, _, _ in rows if ok) / max(1, len(rows))

    def avg_lat(rows):
        vals = [lat for _, ok, lat, _ in rows if ok]
        return statistics.mean(vals) if vals else 0.0

    pre_success = success_rate(pre)
    post_success = success_rate(post)
    pre_lat = avg_lat(pre)
    post_lat = avg_lat(post)

    recovery_s = 0.0
    downtime_s = 0.0
    if kill_time is not None:
        first_success_after_kill = next((t for t, ok, _, _ in post if ok), None)
        if first_success_after_kill is not None:
            recovery_s = max(0.0, first_success_after_kill - kill_time)

        first_fail_after_kill = next((t for t, ok, _, _ in post if not ok), None)
        if first_fail_after_kill is not None:
            first_success_after_fail = next((t for t, ok, _, _ in post if ok and t > first_fail_after_kill), None)
            if first_success_after_fail is not None:
                downtime_s = max(0.0, first_success_after_fail - first_fail_after_kill)

    # Restart worker-2 for next trial
    w2_proc = subprocess.Popen([python_exe, str(repo_root / "app" / "worker.py"), str(w2_port)], cwd=str(repo_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for_http(f"http://127.0.0.1:{w2_port}/health", timeout_s=10)

    return {
        "pre_success": pre_success,
        "post_success": post_success,
        "pre_lat_ms": pre_lat,
        "post_lat_ms": post_lat,
        "recovery_s": recovery_s,
        "downtime_s": downtime_s,
    }, w2_proc


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated repeated fault-injection trials")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--kill-at", type=int, default=40)
    parser.add_argument("--interval", type=float, default=0.05)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    python_exe = sys.executable

    worker_ports = [6101, 6102, 6103]
    balancer_port = 8100
    base_url = f"http://127.0.0.1:{balancer_port}/"

    with tempfile.TemporaryDirectory(prefix="lb_eval_") as tmp:
        tmp_dir = Path(tmp)
        write_temp_config(tmp_dir / "config.yaml", worker_ports, balancer_port)

        w1 = subprocess.Popen([python_exe, str(repo_root / "app" / "worker.py"), str(worker_ports[0])], cwd=str(repo_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        w2 = subprocess.Popen([python_exe, str(repo_root / "app" / "worker.py"), str(worker_ports[1])], cwd=str(repo_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        w3 = subprocess.Popen([python_exe, str(repo_root / "app" / "worker.py"), str(worker_ports[2])], cwd=str(repo_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        balancer = subprocess.Popen([python_exe, str(repo_root / "app" / "balancer.py")], cwd=str(tmp_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        try:
            wait_for_http(f"http://127.0.0.1:{worker_ports[0]}/health")
            wait_for_http(f"http://127.0.0.1:{worker_ports[1]}/health")
            wait_for_http(f"http://127.0.0.1:{worker_ports[2]}/health")
            wait_for_http(base_url)

            rows = []
            for _ in range(args.trials):
                row, w2 = one_trial(base_url, w2, python_exe, repo_root, worker_ports[1], args.requests, args.kill_at, args.interval)
                rows.append(row)

            def m(key: str) -> float:
                return statistics.mean(r[key] for r in rows)

            def s(key: str) -> float:
                return statistics.stdev(r[key] for r in rows) if len(rows) > 1 else 0.0

            print("=" * 72)
            print("FAULT MULTI-RUN SUMMARY")
            print("=" * 72)
            print(f"trials: {args.trials}, requests per trial: {args.requests}, kill_at: {args.kill_at}")
            print(f"pre_success mean +/- std:  {m('pre_success'):.2f}% +/- {s('pre_success'):.2f}")
            print(f"post_success mean +/- std: {m('post_success'):.2f}% +/- {s('post_success'):.2f}")
            print(f"pre_latency mean +/- std:  {m('pre_lat_ms'):.2f} ms +/- {s('pre_lat_ms'):.2f}")
            print(f"post_latency mean +/- std: {m('post_lat_ms'):.2f} ms +/- {s('post_lat_ms'):.2f}")
            print(f"recovery mean +/- std:     {m('recovery_s'):.3f} s +/- {s('recovery_s'):.3f}")
            print(f"downtime mean +/- std:     {m('downtime_s'):.3f} s +/- {s('downtime_s'):.3f}")
        finally:
            for p in [balancer, w1, w2, w3]:
                try:
                    p.terminate()
                    p.wait(timeout=2)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass


if __name__ == "__main__":
    main()
