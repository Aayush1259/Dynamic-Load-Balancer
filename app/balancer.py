"""Dynamic distributed load balancer with health monitoring."""

from flask import Flask, Response, jsonify
import requests
import threading
import time
import logging
import yaml
import signal
import sys
import os
from collections import deque

def load_config(config_file='config.yaml'):
    """Load and validate configuration from YAML file."""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML configuration: {e}")
    
    if not config.get('servers'):
        raise ValueError("Configuration must contain 'servers' list")
    if not config.get('health_check'):
        raise ValueError("Configuration must contain 'health_check' settings")
    if not config.get('load_balancer'):
        raise ValueError("Configuration must contain 'load_balancer' settings")

    health_check = config['health_check']
    if 'interval_seconds' not in health_check or 'timeout_seconds' not in health_check:
        raise ValueError("health_check must include 'interval_seconds' and 'timeout_seconds'")

    load_balancer = config['load_balancer']
    if 'port' not in load_balancer or 'algorithm' not in load_balancer:
        raise ValueError("load_balancer must include 'port' and 'algorithm'")
    
    return config

try:
    CONFIG = load_config()
except (FileNotFoundError, ValueError) as e:
    print(f"Configuration Error: {e}", file=sys.stderr)
    sys.exit(1)

SERVERS = [
    {
        "url": server['url'],
        "name": server.get('name', f"worker-{i}"),
        "active_connections": 0,
        "total_handled": 0,
        "healthy": True,
        "weight": server.get('weight', 1)
    }
    for i, server in enumerate(CONFIG['servers'], 1)
]

METRICS = {
    'start_time': time.time(),
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'queued_requests': 0,
    'response_times': deque(maxlen=1000),
    'requests_by_node': {},
    'health_check_failures': {}
}

METRICS_LOCK = threading.Lock()
SERVERS_LOCK = threading.Lock()

os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=CONFIG['load_balancer'].get('log_level', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/load_balancer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

shutdown_event = threading.Event()

def signal_handler(sig, frame):
    logger.info("Shutting down gracefully...")
    shutdown_event.set()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGTERM, signal_handler)
except (AttributeError, OSError):
    pass

def monitor_nodes():
    """Background daemon that checks backend health via heartbeat."""
    logger.info(f"Health monitor started (interval: {CONFIG['health_check']['interval_seconds']}s)")
    
    while not shutdown_event.is_set():
        with SERVERS_LOCK:
            server_snapshots = [
                (index, server['name'], server['url'])
                for index, server in enumerate(SERVERS)
            ]

        for index, name, url in server_snapshots:
            healthy = False
            error_type = None

            try:
                response = requests.get(
                    f"{url}/health",
                    timeout=CONFIG['health_check']['timeout_seconds']
                )
                healthy = (response.status_code == 200)
            except (requests.ConnectionError, requests.Timeout) as e:
                error_type = type(e).__name__

            with SERVERS_LOCK:
                was_healthy = SERVERS[index]['healthy']
                SERVERS[index]['healthy'] = healthy

            if was_healthy and not healthy:
                reason = f": {error_type}" if error_type else ""
                logger.warning(f"Node {name} ({url}) is now UNHEALTHY{reason}")
                with METRICS_LOCK:
                    METRICS['health_check_failures'][url] = \
                        METRICS['health_check_failures'].get(url, 0) + 1
            elif not was_healthy and healthy:
                logger.info(f"Node {name} ({url}) recovered - now HEALTHY")
        
        time.sleep(CONFIG['health_check']['interval_seconds'])

def select_least_connections_node():
    """Return the healthy node with the fewest weighted active connections, or None."""
    with SERVERS_LOCK:
        healthy_nodes = [s for s in SERVERS if s['healthy']]
        
        if not healthy_nodes:
            return None
        
        target = min(healthy_nodes, key=lambda s: s['active_connections'] / s.get('weight', 1))
        return target

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def distribute_traffic(path):
    """Route request to the least-loaded healthy backend node."""
    start_time = time.time()
    
    with METRICS_LOCK:
        METRICS['total_requests'] += 1
    
    target = select_least_connections_node()
    
    if not target:
        with METRICS_LOCK:
            METRICS['failed_requests'] += 1
            METRICS['queued_requests'] += 1
        
        logger.warning("All backend nodes unavailable!")
        return "Service Temporarily Unavailable - All nodes down.", 503
    
    with SERVERS_LOCK:
        target['active_connections'] += 1
    
    try:
        response = requests.get(f"{target['url']}/{path}", timeout=5)
        response_time = time.time() - start_time
        with METRICS_LOCK:
            METRICS['response_times'].append(response_time)
            METRICS['successful_requests'] += 1
            METRICS['requests_by_node'][target['url']] = \
                METRICS['requests_by_node'].get(target['url'], 0) + 1

        with SERVERS_LOCK:
            target['total_handled'] += 1
        
        logger.debug(f"Request routed to {target['name']} ({response_time*1000:.1f}ms)")
        return Response(response.content, status=response.status_code, 
                       content_type=response.headers.get('content-type', 'text/plain'))
        
    except requests.Timeout:
        with METRICS_LOCK:
            METRICS['failed_requests'] += 1
        logger.error(f"Timeout routing to {target['name']}: Request exceeded 5s limit")
        return "Gateway Timeout - Backend node did not respond in time", 504
        
    except requests.ConnectionError as e:
        with METRICS_LOCK:
            METRICS['failed_requests'] += 1
        logger.error(f"Connection error routing to {target['name']}: {e}")
        with SERVERS_LOCK:
            target['healthy'] = False
        return "Bad Gateway - Backend node unreachable", 502
        
    except Exception as e:
        with METRICS_LOCK:
            METRICS['failed_requests'] += 1
        logger.error(f"Unexpected error routing to {target['name']}: {e}")
        return f"Internal Server Error: {type(e).__name__}", 500
        
    finally:
        with SERVERS_LOCK:
            if target['active_connections'] > 0:
                target['active_connections'] -= 1

@app.route('/metrics')
def get_metrics():
    """Return system and per-node metrics as JSON."""
    with METRICS_LOCK:
        uptime = time.time() - METRICS['start_time']
        response_times = list(METRICS['response_times'])
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        total_req = METRICS['total_requests']
        successful = METRICS['successful_requests']
        failed = METRICS['failed_requests']
        queued = METRICS['queued_requests']
        requests_by_node = dict(METRICS['requests_by_node'])
        health_check_failures = dict(METRICS['health_check_failures'])
    
    with SERVERS_LOCK:
        nodes_data = [
            {
                "name": s['name'],
                "url": s['url'],
                "healthy": s['healthy'],
                "active_connections": s['active_connections'],
                "total_requests": requests_by_node.get(s['url'], 0),
                "health_failures": health_check_failures.get(s['url'], 0),
                "weight": s.get('weight', 1)
            }
            for s in SERVERS
        ]
    
    return jsonify({
        "uptime_seconds": round(uptime, 1),
        "total_requests": total_req,
        "successful_requests": successful,
        "failed_requests": failed,
        "queued_requests": queued,
        "success_rate": f"{(successful/total_req*100) if total_req > 0 else 100:.2f}%",
        "average_response_time_ms": round(avg_response * 1000, 2),
        "requests_per_second": round(total_req / uptime if uptime > 0 else 0, 2),
        "algorithm": "Least Connections",
        "nodes": nodes_data
    })

@app.route('/status')
def status_dashboard():
    """Render the live HTML monitoring dashboard."""
    with METRICS_LOCK:
        uptime = time.time() - METRICS['start_time']
        response_times = list(METRICS['response_times'])
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        success_rate = (METRICS['successful_requests']/METRICS['total_requests']*100) \
                       if METRICS['total_requests'] > 0 else 100
        total_req = METRICS['total_requests']
        requests_by_node = dict(METRICS['requests_by_node'])
        health_check_failures = dict(METRICS['health_check_failures'])
    
    rows = ""
    with SERVERS_LOCK:
        for server in SERVERS:
            status_class = "healthy" if server['healthy'] else "unhealthy"
            status_icon = "✅" if server['healthy'] else "❌"
            total_reqs = requests_by_node.get(server['url'], 0)
            failures = health_check_failures.get(server['url'], 0)
            
            rows += f"""
            <tr class="worker-row {status_class}">
                <td><span class="status-badge {status_class}">{status_icon} {server['name']}</span></td>
                <td><code>{server['url']}</code></td>
                <td><strong>{'HEALTHY' if server['healthy'] else 'DOWN'}</strong></td>
                <td><span class="metric-badge">{server['active_connections']}</span></td>
                <td><span class="metric-badge">{total_reqs}</span></td>
                <td><span class="metric-badge">{failures}</span></td>
                <td><span class="metric-badge">{server.get('weight', 1)}</span></td>
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
        
        code {{
            background: #f1f5f9;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            color: #475569;
        }}
        
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
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
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 600;
            color: #475569;
            display: inline-block;
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
        
        .info-box {{
            background: rgba(255, 255, 255, 0.1);
            border-left: 4px solid #10b981;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            color: white;
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
        
        <div class="info-box">
            <strong>Algorithm:</strong> Least Connections | <strong>Health Interval:</strong> {CONFIG['health_check']['interval_seconds']}s | <strong>Timeout:</strong> {CONFIG['health_check']['timeout_seconds']}s
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{int(uptime)}s</div>
                <div class="metric-label">System Uptime</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{total_req}</div>
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
            <div class="metric-card">
                <div class="metric-value">{len([s for s in SERVERS if s['healthy']])}/{len(SERVERS)}</div>
                <div class="metric-label">Healthy Nodes</div>
            </div>
        </div>
        
        <div class="workers-section">
            <h2 class="section-title">
                <span>⚡</span> Backend Worker Nodes Status
            </h2>
            <table>
                <thead>
                    <tr>
                        <th>Node Name</th>
                        <th>URL</th>
                        <th>Status</th>
                        <th>Active Conn.</th>
                        <th>Total Requests</th>
                        <th>Health Failures</th>
                        <th>Weight</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p><a href="/metrics">📊 JSON Metrics API</a></p>
            <p style="margin-top: 10px; opacity: 0.8;">TCSS 558 - Applied Distributed Computing | Dynamic Load Balancer v2.0</p>
        </div>
    </div>
</body>
</html>
    """
    return html

if __name__ == "__main__":
    try:
        logger.info("Starting health monitor...")
        monitor_thread = threading.Thread(target=monitor_nodes, daemon=True)
        monitor_thread.start()
        
        print("\n" + "="*80)
        print("   🚀 INTELLIGENT LOAD BALANCER - STARTING")
        print("="*80)
        print(f"   Backend Nodes: {len(SERVERS)}")
        for server in SERVERS:
            print(f"     - {server['name']}: {server['url']} (weight: {server.get('weight', 1)})")
        print(f"\n   Algorithm: {CONFIG['load_balancer']['algorithm']}")
        print(f"   Health Check Interval: {CONFIG['health_check']['interval_seconds']}s")
        print(f"   Health Check Timeout: {CONFIG['health_check']['timeout_seconds']}s")
        print(f"   Log Level: {CONFIG['load_balancer']['log_level']}")
        print(f"\n   📊 Dashboard: http://127.0.0.1:{CONFIG['load_balancer']['port']}/status")
        print(f"   📈 Metrics API: http://127.0.0.1:{CONFIG['load_balancer']['port']}/metrics")
        print("="*80 + "\n")
        
        logger.info(f"Load Balancer started on port {CONFIG['load_balancer']['port']}")
        app.run(port=CONFIG['load_balancer']['port'], debug=False, threaded=True)
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Load Balancer shutdown complete")
