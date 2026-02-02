"""
Dynamic Distributed Load Balancer with Health Monitoring
Author: Aayush Modi | Course: TCSS 558 - Applied Distributed Computing

Features:
- Least Connections algorithm for intelligent load distribution
- Automated health monitoring with pull-based heartbeats
- Real-time metrics tracking and visualization
- Professional web dashboard for system monitoring
"""

from flask import Flask, request, Response, jsonify
import requests
import threading
import time
import logging

# ============================================================================
# CONFIGURATION
# ============================================================================

SERVERS = [
    {"url": "http://127.0.0.1:5001", "active_connections": 0, "healthy": True},
    {"url": "http://127.0.0.1:5002", "active_connections": 0, "healthy": True},
    {"url": "http://127.0.0.1:5003", "active_connections": 0, "healthy": True}
]

METRICS = {
    'start_time': time.time(),
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'response_times': [],
    'requests_by_node': {},
    'health_check_failures': {}
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/load_balancer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================================
# HEALTH MONITORING
# ============================================================================

def monitor_nodes():
    """
    Background service that continuously monitors backend node health.
    Checks every 5 seconds with 2-second timeout for quick failure detection.
    """
    logger.info("Health monitor started")
    
    while True:
        for server in SERVERS:
            try:
                response = requests.get(f"{server['url']}/health", timeout=2)
                was_healthy = server['healthy']
                server['healthy'] = (response.status_code == 200)
                
                # Log status changes
                if was_healthy and not server['healthy']:
                    logger.warning(f"Node {server['url']} is now UNHEALTHY")
                elif not was_healthy and server['healthy']:
                    logger.info(f"Node {server['url']} recovered - now HEALTHY")
                    
            except (requests.ConnectionError, requests.Timeout):
                if server['healthy']:
                    logger.warning(f"Node {server['url']} failed health check")
                server['healthy'] = False
                METRICS['health_check_failures'][server['url']] = \
                    METRICS['health_check_failures'].get(server['url'], 0) + 1
        
        time.sleep(5)

# ============================================================================
# LOAD BALANCING
# ============================================================================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def distribute_traffic(path):
    """
    Routes incoming requests using Least Connections algorithm.
    Automatically excludes unhealthy nodes for zero-downtime fault tolerance.
    """
    start_time = time.time()
    METRICS['total_requests'] += 1
    
    # Filter for healthy nodes only
    healthy_nodes = [s for s in SERVERS if s['healthy']]
    
    if not healthy_nodes:
        METRICS['failed_requests'] += 1
        logger.error("All backend nodes unavailable!")
        return "Service Temporarily Unavailable - All nodes down", 503
    
    # Select node with least active connections
    target = min(healthy_nodes, key=lambda s: s['active_connections'])
    target['active_connections'] += 1
    
    try:
        # Proxy request to selected backend
        response = requests.get(f"{target['url']}/{path}", timeout=5)
        
        # Track metrics
        response_time = time.time() - start_time
        METRICS['response_times'].append(response_time)
        METRICS['successful_requests'] += 1
        METRICS['requests_by_node'][target['url']] = \
            METRICS['requests_by_node'].get(target['url'], 0) + 1
        
        logger.info(f"Request routed to {target['url']} ({response_time*1000:.1f}ms)")
        return Response(response.content, status=response.status_code)
        
    except Exception as e:
        METRICS['failed_requests'] += 1
        logger.error(f"Error routing to {target['url']}: {e}")
        return f"Routing Error: {str(e)}", 500
        
    finally:
        target['active_connections'] -= 1

# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@app.route('/metrics')
def get_metrics():
    """JSON API endpoint for programmatic access to metrics"""
    uptime = time.time() - METRICS['start_time']
    avg_response = sum(METRICS['response_times']) / len(METRICS['response_times']) \
                   if METRICS['response_times'] else 0
    
    return jsonify({
        "uptime_seconds": round(uptime, 1),
        "total_requests": METRICS['total_requests'],
        "successful_requests": METRICS['successful_requests'],
        "failed_requests": METRICS['failed_requests'],
        "success_rate": f"{(METRICS['successful_requests']/METRICS['total_requests']*100) if METRICS['total_requests'] > 0 else 100:.2f}%",
        "average_response_time_ms": round(avg_response * 1000, 2),
        "requests_per_second": round(METRICS['total_requests'] / uptime if uptime > 0 else 0, 2),
        "nodes": [
            {
                "url": s['url'],
                "healthy": s['healthy'],
                "active_connections": s['active_connections'],
                "total_requests": METRICS['requests_by_node'].get(s['url'], 0),
                "health_failures": METRICS['health_check_failures'].get(s['url'], 0)
            }
            for s in SERVERS
        ]
    })

@app.route('/status')
def status_dashboard():
    """Beautiful HTML dashboard for real-time system monitoring"""
    uptime = time.time() - METRICS['start_time']
    avg_response = sum(METRICS['response_times']) / len(METRICS['response_times']) \
                   if METRICS['response_times'] else 0
    success_rate = (METRICS['successful_requests']/METRICS['total_requests']*100) \
                   if METRICS['total_requests'] > 0 else 100
    
    # Build worker table rows
    rows = ""
    for server in SERVERS:
        status_class = "healthy" if server['healthy'] else "unhealthy"
        status_icon = "✅" if server['healthy'] else "❌"
        total_reqs = METRICS['requests_by_node'].get(server['url'], 0)
        failures = METRICS['health_check_failures'].get(server['url'], 0)
        
        rows += f"""
            <tr class="worker-row {status_class}">
                <td><span class="status-badge {status_class}">{status_icon} {server['url']}</span></td>
                <td><strong>{'HEALTHY' if server['healthy'] else 'DOWN'}</strong></td>
                <td><span class="metric-badge">{server['active_connections']}</span></td>
                <td><span class="metric-badge">{total_reqs}</span></td>
                <td><span class="metric-badge">{failures}</span></td>
            </tr>
        """
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="5">
    <title>Load Balancer Dashboard | TCSS 558 Project</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        
        .header .subtitle {{
            color: #64748b;
            font-size: 1.1rem;
        }}
        
        .timestamp {{
            margin-top: 15px;
            color: #94a3b8;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 25px;
            border-radius: 16px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #667eea;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        }}
        
        .metric-value {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        
        .metric-label {{
            color: #64748b;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }}
        
        .workers-section {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}
        
        .section-title {{
            font-size: 1.5rem;
            color: #1e293b;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
        }}
        
        thead tr {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        
        th {{
            padding: 15px;
            text-align: left;
            color: white;
            font-weight: 600;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        th:first-child {{
            border-top-left-radius: 12px;
        }}
        
        th:last-child {{
            border-top-right-radius: 12px;
        }}
        
        .worker-row {{
            transition: background 0.2s;
        }}
        
        .worker-row:hover {{
            background: #f8fafc !important;
        }}
        
        .worker-row.healthy {{
            background: rgba(16, 185, 129, 0.05);
        }}
        
        .worker-row.unhealthy {{
            background: rgba(239, 68, 68, 0.05);
        }}
        
        td {{
            padding: 15px;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-family: 'Courier New', monospace;
            font-weight: 600;
        }}
        
        .status-badge.healthy {{
            color: #10b981;
        }}
        
        .status-badge.unhealthy {{
            color: #ef4444;
        }}
        
        .metric-badge {{
            background: #f1f5f9;
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 600;
            color: #475569;
        }}
        
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.9rem;
        }}
        
        .footer a {{
            color: white;
            text-decoration: underline;
        }}
        
        .pulse {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            animation: pulse 2s ease-in-out infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Load Balancer Dashboard</h1>
            <p class="subtitle">Intelligent Traffic Distribution with Automated Health Monitoring</p>
            <div class="timestamp">
                <span class="pulse"></span>
                Last Updated: {time.strftime('%Y-%m-%d %H:%M:%S')} | Auto-refresh: 5s
            </div>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{int(uptime)}s</div>
                <div class="metric-label">System Uptime</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{METRICS['total_requests']}</div>
                <div class="metric-label">Total Requests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{avg_response*1000:.1f}ms</div>
                <div class="metric-label">Avg Response Time</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{success_rate:.1f}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
        </div>
        
        <div class="workers-section">
            <h2 class="section-title">
                <span>⚡</span> Backend Worker Nodes
            </h2>
            <table>
                <thead>
                    <tr>
                        <th>Worker URL</th>
                        <th>Status</th>
                        <th>Active Connections</th>
                        <th>Total Requests</th>
                        <th>Health Failures</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Algorithm: Least Connections | Health Checks: Every 5s | <a href="/metrics">JSON API</a></p>
            <p style="margin-top: 10px; opacity: 0.8;">TCSS 558 - Applied Distributed Computing | Aayush Modi</p>
        </div>
    </div>
</body>
</html>
    """
    return html

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Start health monitor in background
    logger.info("Starting health monitor...")
    threading.Thread(target=monitor_nodes, daemon=True).start()
    
    # Display startup banner
    print("\n" + "="*70)
    print("   🚀 INTELLIGENT LOAD BALANCER - READY")
    print("="*70)
    print(f"   Backend Nodes: {len(SERVERS)}")
    print(f"   Algorithm: Least Connections")
    print(f"   Health Checks: Every 5 seconds")
    print(f"   Metrics API: http://127.0.0.1:8000/metrics")
    print(f"   Dashboard: http://127.0.0.1:8000/status")
    print("="*70 + "\n")
    
    logger.info("Load Balancer started on port 8000")
    app.run(port=8000)
