"""
A simplified health check endpoint that doesn't reveal sensitive information.
This is safe to expose publically on your production server.
"""

import os
import sys
import json
from datetime import datetime
from flask import Flask

app = Flask(__name__)

@app.route('/health')
def basic_health_check():
    """Return basic health information"""
    health_data = {
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": os.environ.get("FLASK_ENV", "production")
    }
    return json.dumps(health_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
