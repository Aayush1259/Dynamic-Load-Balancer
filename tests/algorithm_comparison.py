"""
Algorithm Comparison: Least Connections vs Round Robin

This script demonstrates why Least Connections is superior to Round Robin
for workloads with variable request processing times.

"""

import asyncio
import aiohttp
import time
import random
from collections import Counter
import json

class LoadBalancerSimulator:
    """Simulates load balancer with different algorithms"""
    
    def __init__(self, num_workers=3):
        self.workers = [
            {"id": i, "active_connections": 0, "total_requests": 0}
            for i in range(num_workers)
        ]
        self.round_robin_index = 0
    
    def round_robin_select(self):
        """Round Robin: Sequential selection"""
        worker = self.workers[self.round_robin_index]
        self.round_robin_index = (self.round_robin_index + 1) % len(self.workers)
        return worker
    
    def least_connections_select(self):
        """Least Connections: Select worker with fewest active connections"""
        return min(self.workers, key=lambda w: w['active_connections'])
    
    def reset(self):
        """Reset all counters"""
        for worker in self.workers:
            worker['active_connections'] = 0
            worker['total_requests'] = 0
        self.round_robin_index = 0

async def simulate_request(worker, duration_ms):
    """Simulate a single request with given duration"""
    worker['active_connections'] += 1
    worker['total_requests'] += 1
    await asyncio.sleep(duration_ms / 1000)  # Convert to seconds
    worker['active_connections'] -= 1

async def run_workload(algorithm_name, selection_func, request_durations):
    """
    Run workload simulation with specified algorithm
    
    Args:
        algorithm_name: Name of the algorithm
        selection_func: Function to select worker
        request_durations: List of request durations in milliseconds
    """
    print(f"\n{'='*70}")
    print(f"  Testing: {algorithm_name}")
    print(f"{'='*70}")
    
    lb = LoadBalancerSimulator(num_workers=3)
    tasks = []
    start_time = time.time()
    
    # Schedule all requests
    for duration in request_durations:
        worker = selection_func(lb)
        task = asyncio.create_task(simulate_request(worker, duration))
        tasks.append(task)
        await asyncio.sleep(0.01)  # Small delay between request arrivals
    
    # Wait for all requests to complete
    await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # Calculate metrics
    distribution = [w['total_requests'] for w in lb.workers]
    max_load = max(distribution)
    min_load = min(distribution)
    load_variance = max_load - min_load
    
    # Print results
    print(f"\nResults:")
    print(f"  Total Time: {total_time:.2f} seconds")
    print(f"  Requests per Worker:")
    for i, worker in enumerate(lb.workers):
        bar = '█' * worker['total_requests']
        print(f"    Worker {i}: {worker['total_requests']:3d} requests {bar}")
    
    print(f"\n  Load Distribution:")
    print(f"    Max Load: {max_load} requests")
    print(f"    Min Load: {min_load} requests")
    print(f"    Variance: {load_variance} requests")
    print(f"    Imbalance: {(load_variance/max_load*100) if max_load > 0 else 0:.1f}%")
    
    return {
        "algorithm": algorithm_name,
        "total_time": round(total_time, 2),
        "distribution": distribution,
        "max_load": max_load,
        "min_load": min_load,
        "variance": load_variance,
        "imbalance_percent": round((load_variance/max_load*100) if max_load > 0 else 0, 2)
    }

async def main():
    """Main comparison test"""
    print("="*70)
    print("  ALGORITHM COMPARISON TEST")
    print("  Least Connections vs. Round Robin")
    print("="*70)
    
    # Test Scenario: Variable request durations
    # Simulates real-world scenario where some requests are slow (database queries)
    # and others are fast (static content)
    print("\n📊 Test Scenario: Variable Request Durations")
    print("-" * 70)
    print("Simulating 100 requests with mixed processing times:")
    print("  - 30 fast requests (10-50ms) - e.g., static content")
    print("  - 40 medium requests (100-300ms) - e.g., API calls")
    print("  - 30 slow requests (500-1000ms) - e.g., database queries")
    
    # Generate mixed workload
    fast_requests = [random.randint(10, 50) for _ in range(30)]
    medium_requests = [random.randint(100, 300) for _ in range(40)]
    slow_requests = [random.randint(500, 1000) for _ in range(30)]
    
    request_durations = fast_requests + medium_requests + slow_requests
    random.shuffle(request_durations)  # Randomize order
    
    print(f"\nTotal Requests: {len(request_durations)}")
    print(f"Average Duration: {sum(request_durations)/len(request_durations):.1f}ms")
    
    # Test 1: Round Robin
    results_rr = await run_workload(
        "Round Robin",
        lambda lb: lb.round_robin_select(),
        request_durations.copy()
    )
    
    await asyncio.sleep(1)  # Brief pause between tests
    
    # Test 2: Least Connections
    results_lc = await run_workload(
        "Least Connections",
        lambda lb: lb.least_connections_select(),
        request_durations.copy()
    )
    
    # Comparison Summary
    print(f"\n{'='*70}")
    print("  COMPARISON SUMMARY")
    print(f"{'='*70}\n")
    
    print(f"{'Metric':<30} {'Round Robin':>15} {'Least Conn':>15} {'Winner':>10}")
    print("-" * 70)
    
    # Compare metrics
    comparisons = [
        ("Total Time", results_rr['total_time'], results_lc['total_time'], "lower"),
        ("Load Variance", results_rr['variance'], results_lc['variance'], "lower"),
        ("Imbalance %", results_rr['imbalance_percent'], results_lc['imbalance_percent'], "lower")
    ]
    
    winners = {"Round Robin": 0, "Least Connections": 0}
    
    for metric, rr_val, lc_val, better in comparisons:
        if better == "lower":
            winner = "RR" if rr_val < lc_val else "LC"
        else:
            winner = "RR" if rr_val > lc_val else "LC"
        
        if winner == "LC":
            winners["Least Connections"] += 1
        else:
            winners["Round Robin"] += 1
        
        print(f"{metric:<30} {rr_val:>15} {lc_val:>15} {winner:>10}")
    
    print("\n" + "="*70)
    
    if winners["Least Connections"] > winners["Round Robin"]:
        print("🏆 WINNER: Least Connections Algorithm")
        print("\nWhy Least Connections Won:")
        print("  ✓ Better load distribution across workers")
        print("  ✓ Adapts to varying request processing times")
        print("  ✓ Prevents slow workers from being overloaded")
        print("  ✓ More efficient resource utilization")
    else:
        print("🏆 WINNER: Round Robin Algorithm")
    
    print("\n📝 Academic Insight:")
    print("-" * 70)
    print("For homogeneous workloads (all requests take same time),")
    print("Round Robin and Least Connections perform similarly.")
    print("\nFor heterogeneous workloads (variable request durations),")
    print("Least Connections significantly outperforms Round Robin")
    print("by preventing overloading of slower workers.")
    print("\nThis is why modern cloud platforms (AWS, Google Cloud)")
    print("use Least Connections or its variants by default.")
    print("="*70 + "\n")
    
    # Save results
    results = {
        "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "workload": {
            "total_requests": len(request_durations),
            "fast_requests": len(fast_requests),
            "medium_requests": len(medium_requests),
            "slow_requests": len(slow_requests),
            "avg_duration_ms": sum(request_durations) / len(request_durations)
        },
        "round_robin": results_rr,
        "least_connections": results_lc,
        "winner": "Least Connections" if winners["Least Connections"] > winners["Round Robin"] else "Round Robin"
    }
    
    with open('tests/algorithm_comparison_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("Results saved to: tests/algorithm_comparison_results.json\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
