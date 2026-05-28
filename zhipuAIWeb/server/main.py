"""
zhipuAI Web 服务入口（Flask）
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from module3.exceptions import DiagnosisError
from module3.router import bp as module3_bp

ZHIPUAI_WEB_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ZHIPUAI_WEB_ROOT / ".env")

WEB_DIR = ZHIPUAI_WEB_ROOT / "web"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.register_blueprint(module3_bp, url_prefix="/api/v1")


@app.errorhandler(DiagnosisError)
def handle_diagnosis_error(exc: DiagnosisError):
    return jsonify({"detail": exc.message}), exc.status_code


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(WEB_DIR / "css", filename)


@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(WEB_DIR / "js", filename)


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
