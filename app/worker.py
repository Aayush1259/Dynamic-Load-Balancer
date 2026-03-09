"""
Backend Worker Node - Distributed Load Balancer System

This module implements a backend worker node that:
- Processes incoming requests from the load balancer
- Provides a health check endpoint for automated monitoring
- Logs all activity for debugging and analysis

The worker is designed to be horizontally scalable - multiple instances
can be started on different ports to form a distributed backend cluster.
"""

from flask import Flask, jsonify, request
import sys
import logging
import os
import signal
import time

# Get port from command line argument
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5001

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging with proper formatting
logging.basicConfig(
    level=logging.INFO,
    format=f'%(asctime)s - Worker-{PORT} - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/worker_{PORT}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal. Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGTERM, signal_handler)
except (AttributeError, OSError):
    pass

@app.route('/')
def process_request():
    """
    Handle incoming work requests from the load balancer.
    
    This endpoint simulates processing work by returning a response
    indicating which worker processed the request.
    
    Returns:
        str: Response message with worker port information
    """
    # Optional hidden workload control used by evaluation scripts.
    # The balancer does not inspect this value; workers simulate variable cost.
    work_ms_raw = request.args.get('work_ms')
    if work_ms_raw is not None:
        try:
            work_ms = float(work_ms_raw)
            work_ms = max(0.0, min(work_ms, 2000.0))
            time.sleep(work_ms / 1000.0)
        except ValueError:
            pass

    logger.info("Processing request")
    return f"✓ Request processed by Worker on Port {PORT}\n"

@app.route('/health')
def health_check():
    """
    Health check endpoint for load balancer monitoring.
    
    This endpoint is called by the load balancer's health monitoring service
    to determine if this worker node is alive and operational.
    
    Returns:
        JSON: Health status and port information with 200 status code
    """
    logger.debug("Health check requested")
    return jsonify({"status": "healthy", "port": PORT}), 200

@app.route('/info')
def info():
    """
    Informational endpoint providing worker metadata.
    
    Returns:
        JSON: Worker information including port, status, and log location
    """
    return jsonify({
        "port": PORT,
        "status": "operational",
        "log_file": f"logs/worker_{PORT}.log"
    }), 200

if __name__ == "__main__":
    try:
        logger.info(f"Worker node initialization...")
        print(f"\n{'='*60}")
        print(f"   ⚡ Worker Node Online - Port {PORT}")
        print(f"   📊 Health Check: http://127.0.0.1:{PORT}/health")
        print(f"   📋 Info: http://127.0.0.1:{PORT}/info")
        print(f"{'='*60}\n")
        
        logger.info(f"Starting Flask server on port {PORT}")
        app.run(port=PORT, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        logger.info("Worker received keyboard interrupt")
    except Exception as e:
        logger.critical(f"Fatal error in worker: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Worker node shutdown complete")
