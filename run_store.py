#!/usr/bin/env python3
"""
ExamRankers Standalone Web Store Runner
======================================
Runs the ExamRankers digital ebook store HTTP server locally or on any cloud server.
Provides full checkout, offline/online UPI QR generation, payment verification,
PDF ebook instant downloads, and visitor tracking.

Usage:
    python run_store.py
    python run_store.py --port 8080
    python run_store.py --no-browser
"""

import os
import sys
import argparse
import webbrowser
import http.server
from pathlib import Path
from dotenv import load_dotenv

# Ensure app package is importable
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from app.bot import HealthCheckHandler, init_db, DB_PATH
from app.agents.digital_product_agent import DigitalProductPackagingAgent, DEFAULT_PRODUCTS

def run_store(port: int = 8080, open_browser: bool = True):
    init_db()
    packaging_agent = DigitalProductPackagingAgent()
    packaging_agent.init_products_db(DB_PATH)

    server_address = ("0.0.0.0", port)
    server = http.server.ThreadingHTTPServer(server_address, HealthCheckHandler)
    url = f"http://localhost:{port}"

    print("=" * 65)
    print(" 🚀 ExamRankers™ Standalone Digital Bookstore Server")
    print("=" * 65)
    print(f" 🌐 Store URL:        {url}")
    print(f" 🛒 Storefront:       {url}/store")
    print(f" 📊 Visitor Stats:    {url}/api/admin/visitors")
    print(f" 📦 Products API:     {url}/api/products")
    print(f" 💾 Database:         {DB_PATH}")
    print("=" * 65)
    print(" Press Ctrl+C to stop the server.\n")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Store server stopped gracefully.")
    finally:
        server.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ExamRankers Digital Bookstore")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")), help="Port to listen on (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    run_store(port=args.port, open_browser=not args.no_browser)

