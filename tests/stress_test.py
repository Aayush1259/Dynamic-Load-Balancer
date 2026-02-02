"""
Stress Testing Suite for Distributed Load Balancer

This script performs comprehensive load testing to evaluate system performance
under various traffic conditions. Results are used for academic analysis and
comparison with alternative load balancing algorithms.

Usage: python tests/stress_test.py
"""

import asyncio
import aiohttp
import time
import json
from statistics import mean, median, stdev
from datetime import datetime

async def make_request(session, url, request_id):
    """Make a single request and measure response time"""
    start = time.time()
    try:
        async with session.get(url) as response:
            content = await response.text()
            elapsed = time.time() - start
            return {
                'request_id': request_id,
                'elapsed': elapsed,
                'status': response.status,
                'success': response.status == 200,
                'content': content[:50]  # First 50 chars
            }
    except Exception as e:
        elapsed = time.time() - start
        return {
            'request_id': request_id,
            'elapsed': elapsed,
            'status': 0,
            'success': False,
            'error': str(e)
        }

async def stress_test(num_requests, concurrency, test_name):
    """
    Run stress test with specified parameters
    
    Args:
        num_requests: Total number of requests to send
        concurrency: Number of concurrent requests
        test_name: Descriptive name for this test
    """
    url = "http://127.0.0.1:8000"
    results = []
    
    print(f"\n{'='*70}")
    print(f"  STRESS TEST: {test_name}")
    print(f"{'='*70}")
    print(f"Parameters: {num_requests} total requests, {concurrency} concurrent")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    test_start = time.time()
    
    async with aiohttp.ClientSession() as session:
        # Create batches of concurrent requests
        for batch_start in range(0, num_requests, concurrency):
            batch_size = min(concurrency, num_requests - batch_start)
            tasks = [
                make_request(session, url, batch_start + i)
                for i in range(batch_size)
            ]
            
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            # Progress indicator
            progress = (batch_start + batch_size) / num_requests * 100
            print(f"Progress: {progress:.1f}% ({batch_start + batch_size}/{num_requests})", end='\r')
    
    test_duration = time.time() - test_start
    print()  # New line after progress indicator
    
    # Calculate statistics
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    response_times = [r['elapsed'] for r in results]
    successful_times = [r['elapsed'] for r in successful]
    
    print(f"\n{'─'*70}")
    print("  TEST RESULTS")
    print(f"{'─'*70}")
    print(f"Total Requests:          {num_requests}")
    print(f"Successful:              {len(successful)} ({len(successful)/num_requests*100:.1f}%)")
    print(f"Failed:                  {len(failed)} ({len(failed)/num_requests*100:.1f}%)")
    print(f"Total Test Duration:     {test_duration:.2f} seconds")
    print(f"\n{'─'*70}")
    print("  RESPONSE TIME STATISTICS")
    print(f"{'─'*70}")
    
    if successful_times:
        print(f"Average Response Time:   {mean(successful_times)*1000:.2f} ms")
        print(f"Median Response Time:    {median(successful_times)*1000:.2f} ms")
        print(f"Std Deviation:           {stdev(successful_times)*1000:.2f} ms" if len(successful_times) > 1 else "Std Deviation:           N/A")
        print(f"Min Response Time:       {min(successful_times)*1000:.2f} ms")
        print(f"Max Response Time:       {max(successful_times)*1000:.2f} ms")
    else:
        print("No successful requests to analyze")
    
    print(f"\n{'─'*70}")
    print("  THROUGHPUT METRICS")
    print(f"{'─'*70}")
    print(f"Requests/Second:         {num_requests/test_duration:.2f}")
    print(f"Avg Request Duration:    {mean(response_times)*1000:.2f} ms")
    print(f"{'='*70}\n")
    
    # Save results to file
    result_data = {
        'test_name': test_name,
        'timestamp': datetime.now().isoformat(),
        'parameters': {
            'total_requests': num_requests,
            'concurrency': concurrency
        },
        'results': {
            'successful_requests': len(successful),
            'failed_requests': len(failed),
            'success_rate': len(successful)/num_requests*100,
            'total_duration': test_duration,
            'requests_per_second': num_requests/test_duration
        },
        'response_times': {
            'average_ms': mean(successful_times)*1000 if successful_times else 0,
            'median_ms': median(successful_times)*1000 if successful_times else 0,
            'min_ms': min(successful_times)*1000 if successful_times else 0,
            'max_ms': max(successful_times)*1000 if successful_times else 0,
            'std_dev_ms': stdev(successful_times)*1000 if len(successful_times) > 1 else 0
        }
    }
    
    return result_data

async def run_all_tests():
    """Execute comprehensive test suite"""
    print("\n" + "="*70)
    print("  DISTRIBUTED LOAD BALANCER - STRESS TEST SUITE")
    print("="*70)
    print("  Academic Performance Analysis for TCSS 558")
    print("="*70)
    
    all_results = []
    
    # Test 1: Light Load
    result = await stress_test(100, 10, "Light Load - 100 requests, 10 concurrent")
    all_results.append(result)
    
    await asyncio.sleep(2)  # Cooldown between tests
    
    # Test 2: Medium Load
    result = await stress_test(500, 50, "Medium Load - 500 requests, 50 concurrent")
    all_results.append(result)
    
    await asyncio.sleep(2)
    
    # Test 3: Heavy Load
    result = await stress_test(1000, 100, "Heavy Load - 1000 requests, 100 concurrent")
    all_results.append(result)
    
    await asyncio.sleep(2)
    
    # Test 4: Extreme Concurrency
    result = await stress_test(500, 200, "Extreme Concurrency - 500 requests, 200 concurrent")
    all_results.append(result)
    
    # Save all results
    with open('tests/test_results.json', 'w') as f:
        json.dump({
            'test_suite': 'Distributed Load Balancer Performance Analysis',
            'course': 'TCSS 558 - Applied Distributed Computing',
            'execution_time': datetime.now().isoformat(),
            'tests': all_results
        }, f, indent=2)
    
    print("\n" + "="*70)
    print("  ALL TESTS COMPLETED")
    print("="*70)
    print("Results saved to: tests/test_results.json")
    print("="*70 + "\n")
    
    # Summary table
    print("\nSUMMARY TABLE FOR REPORT:\n")
    print(f"{'Test Name':<45} {'Requests/sec':<15} {'Avg Time (ms)':<15} {'Success Rate'}")
    print("─"*90)
    for result in all_results:
        rps = result['results']['requests_per_second']
        avg_time = result['response_times']['average_ms']
        success = result['results']['success_rate']
        name = result['test_name'][:44]
        print(f"{name:<45} {rps:<15.2f} {avg_time:<15.2f} {success:.1f}%")
    print()

if __name__ == "__main__":
    print("\nNOTE: Ensure the Load Balancer and all Worker nodes are running before starting tests.\n")
    
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user.")
    except Exception as e:
        print(f"\n\nError during testing: {str(e)}")
        print("Make sure the load balancer is running on http://127.0.0.1:8000")
