"""
Dynamic Distributed Load Balancer Package

This package implements a production-ready distributed load balancer with:
- Least Connections algorithm for intelligent traffic distribution
- Automated health monitoring with heartbeat mechanism
- Real-time metrics tracking and visualization
- Thread-safe operations for concurrent request handling

Modules:
    - balancer: Main load balancer with health monitoring and request routing
    - worker: Backend worker nodes that process requests

Usage:
    Start workers (in separate terminals):
        python app/worker.py 5001
        python app/worker.py 5002
        python app/worker.py 5003
    
    Start load balancer:
        python app/balancer.py
    
    Access dashboard: http://127.0.0.1:8000/status
    Access metrics: http://127.0.0.1:8000/metrics

Project Information:
    Course: TCSS 558 - Applied Distributed Computing
    Term: Winter 2026
    Concepts: Load Balancing, Fault Tolerance, Distributed Systems
"""

__version__ = "2.0.0"
__author__ = "Aayush Kiratbhai Modi"
__all__ = ['balancer', 'worker']
