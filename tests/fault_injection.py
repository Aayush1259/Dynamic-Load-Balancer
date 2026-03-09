import requests
import time
import argparse

DEFAULT_URL = "http://127.0.0.1:8000/"

def run_fault_test(url=DEFAULT_URL, interval=0.5, timeout=2.0):
    print("="*60)
    print("🛡️  FAULT TOLERANCE / ZERO DOWNTIME TEST")
    print("="*60)
    print(f"Target: {url}")
    print(f"This script will send a request every {interval:.2f} seconds.")
    print("Instructions:")
    print("1. Keep this script running.")
    print("2. Open your terminal where workers are running.")
    print("3. KILL one worker process (Ctrl+C).")
    print("4. Watch this script continue to succeed! (Zero Downtime)")
    print("="*60)
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    counter = 1
    failures = 0
    
    try:
        while True:
            try:
                start = time.time()
                resp = requests.get(url, timeout=timeout)
                duration = (time.time() - start) * 1000
                
                if resp.status_code == 200:
                    print(f"[{counter}] ✅ Success | {duration:.0f}ms | {resp.text.strip()}")
                else:
                    print(f"[{counter}] ❌ Error {resp.status_code} | {resp.text}")
                    failures += 1
                    
            except requests.exceptions.ConnectionError:
                print(f"[{counter}] ❌ Connection Error - Load Balancer Down?")
                failures += 1
            except Exception as e:
                print(f"[{counter}] ❌ Error: {e}")
                failures += 1
                
            counter += 1
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("TEST STOPPED")
        print(f"Total Requests: {counter-1}")
        print(f"Failures:       {failures}")
        if failures == 0:
            print("RESULT: ⭐ PERFECT ZERO DOWNTIME ⭐")
        else:
            print("RESULT: Some failures detected (Normal during instant kill)")
        print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Continuously probe balancer during worker failures")
    parser.add_argument("--url", default=DEFAULT_URL, help="Load balancer URL (default: %(default)s)")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between requests (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=2.0, help="Per-request timeout in seconds (default: %(default)s)")
    args = parser.parse_args()
    run_fault_test(url=args.url, interval=args.interval, timeout=args.timeout)
