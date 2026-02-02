"""
Automated Fault Injection Testing for Load Balancer

This script automatically tests the fault tolerance of the distributed
load balancer by simulating node failures and verifying zero-downtime recovery.

Author: Aayush Modi
Course: TCSS 558 - Applied Distributed Computing
"""

import subprocess
import time
import requests
import sys
from datetime import datetime

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{Colors.END}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.YELLOW}→ {text}{Colors.END}")

def check_service(url, service_name):
    """Check if a service is running"""
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            print_success(f"{service_name} is running")
            return True
        else:
            print_error(f"{service_name} returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"{service_name} is not responding: {e}")
        return False

def send_test_requests(load_balancer_url, num_requests=10):
    """Send multiple requests and track responses"""
    print_info(f"Sending {num_requests} test requests...")
    
    responses = []
    failures = 0
    
    for i in range(num_requests):
        try:
            response = requests.get(load_balancer_url, timeout=2)
            if response.status_code == 200:
                # Extract port from response
                port = response.text.split("Port ")[-1].split()[0]
                responses.append(port)
            else:
                failures += 1
                print_error(f"Request {i+1} failed with status {response.status_code}")
        except Exception as e:
            failures += 1
            print_error(f"Request {i+1} failed: {e}")
        
        time.sleep(0.1)  # Small delay between requests
    
    # Count distribution
    from collections import Counter
    distribution = Counter(responses)
    
    print(f"\n{Colors.BOLD}Request Distribution:{Colors.END}")
    for port, count in sorted(distribution.items()):
        print(f"  Port {port}: {count} requests")
    
    success_rate = ((num_requests - failures) / num_requests) * 100
    print(f"\n{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.END}")
    
    return failures == 0, distribution

def get_metrics(metrics_url):
    """Get current metrics from load balancer"""
    try:
        response = requests.get(metrics_url, timeout=2)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def main():
    """Main test execution"""
    print_header("FAULT INJECTION TEST - Distributed Load Balancer")
    print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    LOAD_BALANCER_URL = "http://127.0.0.1:8000"
    METRICS_URL = "http://127.0.0.1:8000/metrics"
    WORKER_URLS = [
        "http://127.0.0.1:5001",
        "http://127.0.0.1:5002",
        "http://127.0.0.1:5003"
    ]
    
    # Step 1: Verify all services are running
    print_header("STEP 1: Pre-Test System Verification")
    
    if not check_service(LOAD_BALANCER_URL, "Load Balancer"):
        print_error("Load Balancer is not running. Please start it first.")
        print_info("Run: python app/balancer.py")
        sys.exit(1)
    
    for i, url in enumerate(WORKER_URLS, 1):
        if not check_service(f"{url}/health", f"Worker {i}"):
            print_error(f"Worker {i} is not running. Test requires all workers.")
            sys.exit(1)
    
    print_success("All services are operational!")
    
    # Step 2: Baseline testing
    print_header("STEP 2: Baseline Performance Test")
    success, baseline_dist = send_test_requests(LOAD_BALANCER_URL, 20)
    
    if not success:
        print_error("Baseline test failed. Aborting.")
        sys.exit(1)
    
    baseline_metrics = get_metrics(METRICS_URL)
    if baseline_metrics:
        print(f"\nBaseline Metrics:")
        print(f"  Total Requests: {baseline_metrics['total_requests']}")
        print(f"  Success Rate: {baseline_metrics['success_rate']}")
        print(f"  Avg Response Time: {baseline_metrics['average_response_time_ms']:.2f}ms")
    
    # Step 3: Fault Injection
    print_header("STEP 3: Fault Injection - Simulating Node Failure")
    print_info("Instructions:")
    print("  1. In one of your worker terminals (e.g., Port 5001)")
    print("  2. Press Ctrl+C to stop that worker")
    print("  3. Wait for this test to detect the failure\n")
    
    print("Monitoring for node failure...")
    print("(Checking health status every 2 seconds)\n")
    
    initial_healthy = 3
    current_healthy = 3
    detection_time = None
    start_time = time.time()
    
    # Wait for user to kill a worker (max 60 seconds)
    while current_healthy == initial_healthy and (time.time() - start_time) < 60:
        time.sleep(2)
        metrics = get_metrics(METRICS_URL)
        
        if metrics and 'nodes' in metrics:
            current_healthy = sum(1 for node in metrics['nodes'] if node['healthy'])
            
            if current_healthy < initial_healthy:
                detection_time = time.time() - start_time
                failed_node = [node['url'] for node in metrics['nodes'] if not node['healthy']][0]
                print_success(f"Failure detected in {detection_time:.1f} seconds!")
                print_info(f"Failed node: {failed_node}")
                break
            else:
                print(f"  All {current_healthy} nodes still healthy... (waiting)", end='\r')
    
    if current_healthy == initial_healthy:
        print_error("\nNo failure detected within 60 seconds")
        print_info("Please manually stop one worker and re-run this test")
        sys.exit(0)
    
    # Step 4: Test during failure
    print_header("STEP 4: Performance Test During Failure")
    print_info(f"Testing with {current_healthy}/{initial_healthy} nodes operational")
    
    time.sleep(3)  # Wait for health monitor to stabilize
    
    success_during_failure, failure_dist = send_test_requests(LOAD_BALANCER_URL, 20)
    
    if success_during_failure:
        print_success("ZERO DOWNTIME ACHIEVED! All requests succeeded despite node failure")
    else:
        print_error("Some requests failed during node outage")
    
    failure_metrics = get_metrics(METRICS_URL)
    if failure_metrics:
        print(f"\nMetrics During Failure:")
        print(f"  Total Requests: {failure_metrics['total_requests']}")
        print(f"  Success Rate: {failure_metrics['success_rate']}")
        print(f"  Healthy Nodes: {current_healthy}/{initial_healthy}")
    
    # Step 5: Recovery test
    print_header("STEP 5: Recovery Verification")
    print_info("Restart the failed worker now...")
    print_info("Monitoring for recovery (checking every 3 seconds)\n")
    
    recovered = False
    recovery_start = time.time()
    
    while not recovered and (time.time() - recovery_start) < 60:
        time.sleep(3)
        metrics = get_metrics(METRICS_URL)
        
        if metrics and 'nodes' in metrics:
            current_healthy = sum(1 for node in metrics['nodes'] if node['healthy'])
            
            if current_healthy == initial_healthy:
                recovery_time = time.time() - recovery_start
                print_success(f"Full recovery detected in {recovery_time:.1f} seconds!")
                recovered = True
                break
            else:
                print(f"  {current_healthy}/{initial_healthy} nodes healthy... (waiting)", end='\r')
    
    if not recovered:
        print_info("\nRecovery not completed within timeout (expected if node not restarted)")
    
    # Final Summary
    print_header("TEST SUMMARY")
    
    print(f"{Colors.BOLD}Fault Tolerance Metrics:{Colors.END}")
    print(f"  Failure Detection Time: {detection_time:.1f} seconds" if detection_time else "  N/A")
    print(f"  Zero Downtime: {'✓ YES' if success_during_failure else '✗ NO'}")
    print(f"  Requests During Failure: 100% success" if success_during_failure else "  Some failures")
    print(f"  Auto Recovery: {'✓ YES' if recovered else 'Not tested'}")
    
    print(f"\n{Colors.BOLD}Load Distribution:{Colors.END}")
    print(f"  Baseline (3 nodes): {dict(baseline_dist)}")
    print(f"  During Failure ({current_healthy} nodes): {dict(failure_dist)}")
    
    print(f"\n{Colors.BOLD}Conclusion:{Colors.END}")
    if success_during_failure:
        print_success("System demonstrates production-grade fault tolerance!")
        print_success("Users experience ZERO downtime during node failures")
    else:
        print_error("System requires improvements to achieve zero downtime")
    
    print(f"\nTest Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.END}")
        sys.exit(1)
