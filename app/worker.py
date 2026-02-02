"""
Backend Worker Node
Simple Flask server that processes requests and provides health status
"""

from flask import Flask, jsonify
import sys
import logging

# Get port from command line argument
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5001

# Configure logging
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

@app.route('/')
def process_request():
    """Handle incoming work requests"""
    logger.info(f"Processing request")
    return f"✓ Request processed by Worker on Port {PORT}\n"

@app.route('/health')
def health_check():
    """Health check endpoint for load balancer monitoring"""
    return jsonify({"status": "healthy", "port": PORT}), 200

if __name__ == "__main__":
    logger.info(f"Worker node starting...")
    print(f"\n{'='*60}")
    print(f"   ⚡ Worker Node Online - Port {PORT}")
    print(f"{'='*60}\n")
    app.run(port=PORT)
