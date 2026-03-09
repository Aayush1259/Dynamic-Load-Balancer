import random
import statistics
import argparse

def simulate_algorithm_comparison(total_requests=100, seed=42):
    random.seed(seed)

    print("="*60)
    print("⚖️  ALGORITHM STATUS COMPARISON: LC vs Round Robin")
    print("="*60)
    
    # Simulation Data
    requests = total_requests
    servers = ['S1', 'S2', 'S3']
    
    # Round Robin Simulation
    rr_load = {'S1': 0, 'S2': 0, 'S3': 0}
    for i in range(requests):
        server = servers[i % len(servers)]
        rr_load[server] += 1
        
    # Least Connections Simulation (Simulated Random Release)
    lc_load = {'S1': 0, 'S2': 0, 'S3': 0}
    current_conns = {'S1': 0, 'S2': 0, 'S3': 0}
    
    for i in range(requests):
        # Select server with min connections
        target = min(current_conns, key=current_conns.get)
        lc_load[target] += 1
        current_conns[target] += 1
        
        # Simulate request completion (randomly free connection)
        if i % 3 == 0:
            freed = random.choice(servers)
            if current_conns[freed] > 0:
                current_conns[freed] -= 1

    print("\n1. Round Robin (RR) Load Distribution:")
    for s in servers:
        print(f"   - {s}: {rr_load[s]} requests")
    print(f"   > Variance: {statistics.variance(rr_load.values()):.2f}")
    
    print("\n2. Least Connections (LC) Load Distribution:")
    for s in servers:
        print(f"   - {s}: {lc_load[s]} requests")
    print(f"   > Variance: {statistics.variance(lc_load.values()):.2f}")
    
    print("\n🏆 CONCLUSION:")
    print("   Least Connections adapts dynamically to load.")
    print("   Round Robin is static and can overwhelm servers.")
    print(f"   (Seed: {seed})")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare RR vs LC scheduling simulation")
    parser.add_argument("--requests", type=int, default=100, help="Number of simulated requests (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: %(default)s)")
    args = parser.parse_args()
    simulate_algorithm_comparison(total_requests=args.requests, seed=args.seed)
