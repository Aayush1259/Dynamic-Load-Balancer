import requests
import concurrent.futures
import time
import statistics
import argparse

DEFAULT_URL = "http://127.0.0.1:8000/"

def send_request(url):
    try:
        start = time.time()
        resp = requests.get(url, timeout=5)
        duration = time.time() - start
        return (resp.status_code, duration)
    except Exception as e:
        return (str(e), 0)

def run_stress_test(url=DEFAULT_URL, total_requests=100, concurrency=10):
    print(f"🚀 STARTING STRESS TEST")
    print(f"Target: {url}")
    print(f"Goal: {total_requests} requests with {concurrency} concurrent threads")
    print("-" * 50)
    
    successful = 0
    failed = 0
    durations = []
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_request, url) for _ in range(total_requests)]
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            status, duration = future.result()
            if status == 200:
                successful += 1
                durations.append(duration)
            else:
                failed += 1
            
            if (i+1) % 50 == 0:
                print(f"   Progress: {i+1}/{total_requests} completed...")
                
    total_time = time.time() - start_time
    
    print("-" * 50)
    print(f"📊 RESULTS:")
    print(f"   ✅ Successful: {successful}")
    print(f"   ❌ Failed:     {failed}")
    print(f"   ⏱️  Total Time: {total_time:.2f}s")
    print(f"   🚀 Throughput: {successful/total_time:.1f} req/s")
    if durations:
        print(f"   ⚡ Avg Latency: {statistics.mean(durations)*1000:.1f}ms")
        print(f"   📏 P95 Latency: {statistics.quantiles(durations, n=20)[18]*1000:.1f}ms" if len(durations) >= 20 else "   📏 P95 Latency: N/A (need >= 20 samples)")
    print("-" * 50)

def parse_args():
    parser = argparse.ArgumentParser(description="Run load-balancer stress test")
    parser.add_argument("--url", default=DEFAULT_URL, help="Load balancer URL (default: %(default)s)")
    parser.add_argument("--requests", type=int, default=500, help="Total requests to send (default: %(default)s)")
    parser.add_argument("--concurrency", type=int, default=50, help="Concurrent workers (default: %(default)s)")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_stress_test(url=args.url, total_requests=args.requests, concurrency=args.concurrency)
