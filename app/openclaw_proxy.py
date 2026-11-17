"""
OpenClaw Gateway Isolated Proxy & Dedicated Service Link Handler.
Provides a completely isolated gateway and reverse-proxy for OpenClaw (installed from https://github.com/openclaw/openclaw.git)
without entangling with the core ExamRankers Rank Bot and Digital Bookstore platform.
"""

import html
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

OPENCLAW_REPO_URL = "https://github.com/openclaw/openclaw.git"
OPENCLAW_GATEWAY_URL_ENV = os.getenv("OPENCLAW_GATEWAY_URL", "").strip()
if OPENCLAW_GATEWAY_URL_ENV:
    if not OPENCLAW_GATEWAY_URL_ENV.startswith(("http://", "https://")):
        OPENCLAW_GATEWAY_BASE_URL = f"https://{OPENCLAW_GATEWAY_URL_ENV.rstrip('/')}"
    else:
        OPENCLAW_GATEWAY_BASE_URL = OPENCLAW_GATEWAY_URL_ENV.rstrip("/")
    OPENCLAW_IS_REMOTE = True
    OPENCLAW_GATEWAY_PORT = 8080
    OPENCLAW_GATEWAY_HOST = urllib.parse.urlparse(OPENCLAW_GATEWAY_BASE_URL).hostname or "openclaw"
else:
    OPENCLAW_GATEWAY_PORT = int(os.getenv("OPENCLAW_GATEWAY_PORT", "18789"))
    OPENCLAW_GATEWAY_HOST = os.getenv("OPENCLAW_GATEWAY_HOST", "127.0.0.1")
    OPENCLAW_GATEWAY_BASE_URL = f"http://{OPENCLAW_GATEWAY_HOST}:{OPENCLAW_GATEWAY_PORT}"
    OPENCLAW_IS_REMOTE = False

_GATEWAY_PROCESS: Optional[subprocess.Popen] = None
_PROCESS_LOCK = threading.Lock()


def is_openclaw_cli_available() -> Tuple[bool, str]:
    """Checks whether the official OpenClaw binary is on PATH."""
    bin_path = (
        shutil.which("openclaw")
        or shutil.which("openclaw.cmd")
        or shutil.which("openclaw.exe")
    )
    if bin_path:
        return True, bin_path
    return False, ""


def is_gateway_online(timeout_sec: float = 0.5) -> bool:
    """Probes the OpenClaw Gateway port on loopback or remote Render URL."""
    if OPENCLAW_IS_REMOTE:
        try:
            with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
                r = client.get(OPENCLAW_GATEWAY_BASE_URL)
                return r.status_code < 500
        except Exception:
            return False
    try:
        with socket.create_connection((OPENCLAW_GATEWAY_HOST, OPENCLAW_GATEWAY_PORT), timeout=timeout_sec):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def start_gateway_background(port: int = OPENCLAW_GATEWAY_PORT) -> Dict[str, Any]:
    """Starts the official OpenClaw gateway daemon in the background."""
    global _GATEWAY_PROCESS
    with _PROCESS_LOCK:
        if is_gateway_online():
            return {"success": True, "message": f"OpenClaw Gateway already active on port {port}.", "online": True}

        installed, bin_path = is_openclaw_cli_available()
        if not installed:
            return {
                "success": False,
                "message": f"OpenClaw binary not found. Install from official source: {OPENCLAW_REPO_URL}",
                "online": False
            }

        try:
            cmd = [bin_path, "gateway", "run", "--port", str(port)]
            _GATEWAY_PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )
            # Give it a second to bind
            time.sleep(1.0)
            online = is_gateway_online(1.0)
            return {
                "success": True,
                "message": f"Launched OpenClaw Gateway (PID: {_GATEWAY_PROCESS.pid}) on port {port}.",
                "online": online
            }
        except Exception as e:
            logger.error(f"Failed to start OpenClaw gateway: {e}")
            return {"success": False, "message": str(e), "online": False}


def render_openclaw_portal_html(base_url: str = "") -> str:
    """Renders the standalone OpenClaw dedicated link interface."""
    online = is_gateway_online(0.3)
    cli_avail, cli_path = is_openclaw_cli_available()

    if OPENCLAW_IS_REMOTE:
        status_badge = (
            f'<span style="background:#059669; color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:12px;">🟢 Remote Gateway Live ({html.escape(OPENCLAW_GATEWAY_BASE_URL)})</span>'
            if online else
            f'<span style="background:#f59e0b; color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:12px;">🟡 Remote Gateway Connecting ({html.escape(OPENCLAW_GATEWAY_BASE_URL)})</span>'
        )
    else:
        status_badge = (
            f'<span style="background:#059669; color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:12px;">🟢 Gateway Online (Port {OPENCLAW_GATEWAY_PORT})</span>'
            if online else
            '<span style="background:#dc2626; color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:12px;">🔴 Gateway Offline</span>'
        )

    cli_badge = (
        f'<span style="color:#10b981; font-weight:700;">✅ Installed ({html.escape(cli_path)})</span>'
        if cli_avail else
        '<span style="color:#f59e0b; font-weight:700;">⚠️ Not Installed (Ready to install from GitHub)</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="mr" class="h-full bg-slate-900 text-slate-100">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>OpenClaw Official Gateway — Dedicated Render Link</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #090d16;
            --bg-card: #0f172a;
            --border: #1e293b;
            --accent-purple: #8b5cf6;
            --accent-cyan: #38bdf8;
            --accent-gold: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg-base);
            color: #f8fafc;
            font-family: 'Plus Jakarta Sans', 'Noto Sans Devanagari', sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 20px;
        }}
        .container {{
            max-width: 860px;
            margin: 0 auto;
            width: 100%;
        }}
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.5);
            margin-bottom: 20px;
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 20px;
        }}
        .brand-title {{
            font-size: 20px;
            font-weight: 800;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            border: none;
            text-decoration: none;
            transition: all 0.2s;
            min-height: 44px;
        }}
        .btn-purple {{ background: linear-gradient(135deg, #7c3aed, #6366f1); color: #fff; }}
        .btn-purple:hover {{ opacity: 0.95; transform: translateY(-1px); }}
        .btn-outline {{ background: transparent; border: 1px solid var(--border); color: #cbd5e1; }}
        .btn-outline:hover {{ border-color: #64748b; color: #fff; }}
        .btn-green {{ background: #059669; color: #fff; }}
        .code-box {{
            background: #020617;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 14px;
            font-family: monospace;
            font-size: 12.5px;
            color: #38bdf8;
            overflow-x: auto;
            margin: 12px 0;
            line-height: 1.6;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 14px;
            margin-top: 16px;
        }}
        .info-pill {{
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 14px;
        }}
        @media (max-width: 640px) {{
            body {{ padding: 12px; }}
            .card {{ padding: 16px; }}
            .btn {{ width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Main Service Card -->
        <div class="card">
            <div class="header">
                <div>
                    <div class="brand-title">
                        <span>🦞</span> OpenClaw Official Gateway
                    </div>
                    <div style="font-size:12px; color:#94a3b8; margin-top:4px;">
                        अधिकृत ओपनसोर्स OpenClaw फ्रेमवर्क — स्वतंत्र लिंक व स्वतंत्र व्यवस्थापन
                    </div>
                </div>
                <div>
                    {status_badge}
                </div>
            </div>

            <!-- Architecture Isolation Banner -->
            <div style="background:rgba(124, 58, 237, 0.12); border:1px solid rgba(139, 92, 246, 0.4); border-radius:10px; padding:14px; margin-bottom:18px;">
                <div style="font-weight:700; color:#c4b5fd; font-size:13.5px; display:flex; align-items:center; gap:8px;">
                    <span>🛡️</span> <b>१००% स्वतंत्र व सुरक्षित आर्किटेक्चर (Total Architecture Separation):</b>
                </div>
                <div style="font-size:12px; color:#cbd5e1; margin-top:6px; line-height:1.5;">
                    आपला <b>ExamRankers Rank Bot, डिजिटल स्टोअर व ॲडमिन स्टुडिओ</b> पूर्णपणे वेगळा आणि क्लीन ठेवण्यात आला आहे. OpenClaw हे त्याच्या अधिकृत GitHub सोर्सवरून (<a href="{OPENCLAW_REPO_URL}" target="_blank" style="color:#38bdf8; text-decoration:underline;">{OPENCLAW_REPO_URL}</a>) स्वतंत्र पोर्ट/लिंकवर कार्य करते.
                </div>
            </div>

            <!-- Current Telemetry Grid -->
            <div class="grid-2">
                <div class="info-pill">
                    <div style="font-size:11px; color:#94a3b8; text-transform:uppercase; font-weight:700;">अधिकृत सोर्स (Official Source)</div>
                    <div style="font-size:13px; font-weight:700; color:#f8fafc; margin-top:4px;">
                        <a href="{OPENCLAW_REPO_URL}" target="_blank" style="color:#38bdf8; text-decoration:none;">openclaw/openclaw.git ↗</a>
                    </div>
                </div>
                <div class="info-pill">
                    <div style="font-size:11px; color:#94a3b8; text-transform:uppercase; font-weight:700;">गेटवे पोर्ट व सॉकेट (Target Port)</div>
                    <div style="font-size:13px; font-weight:700; color:#f8fafc; margin-top:4px;">
                        127.0.0.1:{OPENCLAW_GATEWAY_PORT} (Loopback)
                    </div>
                </div>
                <div class="info-pill">
                    <div style="font-size:11px; color:#94a3b8; text-transform:uppercase; font-weight:700;">CLI बायनरी स्थिती (OpenClaw CLI)</div>
                    <div style="font-size:13px; margin-top:4px;">
                        {cli_badge}
                    </div>
                </div>
                <div class="info-pill">
                    <div style="font-size:11px; color:#94a3b8; text-transform:uppercase; font-weight:700;">स्वतंत्र वेब लिंक (Separate Route)</div>
                    <div style="font-size:13px; font-weight:700; color:#a78bfa; margin-top:4px;">
                        <code>/openclaw/</code>
                    </div>
                </div>
            </div>

            <!-- Action Controls -->
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:20px; align-items:center;">
                <button class="btn btn-purple" onclick="startGateway()" id="startBtn">⚡ Start OpenClaw Gateway</button>
                <button class="btn btn-outline" onclick="checkStatus()">🔄 Refresh Status</button>
                <a href="/" class="btn btn-outline">📚 Back to ExamRankers Store</a>
                <a href="/admin" class="btn btn-outline">🎛️ Admin Studio</a>
            </div>

            <!-- Terminal / Output Log -->
            <div style="margin-top:20px;">
                <div style="font-size:12px; font-weight:700; color:#94a3b8; margin-bottom:6px;">📡 गेटवे कन्सोल लॉग (Gateway Diagnostics):</div>
                <div id="portalLog" class="code-box">
                    [System Ready] OpenClaw Dedicated Link Mounted at /openclaw/
                    Target: http://127.0.0.1:{OPENCLAW_GATEWAY_PORT}/
                    Source: {OPENCLAW_REPO_URL}
                </div>
            </div>
        </div>

        <!-- Render Deployment Blueprint Card -->
        <div class="card">
            <h3 style="font-size:16px; font-weight:800; color:#fff; margin-bottom:10px; display:flex; align-items:center; gap:8px;">
                <span>☁️</span> Render वर स्वतंत्र OpenClaw Deploy करण्याचे २ पर्याय (2 Ways to Deploy on Render):
            </h3>

            <div style="margin-top:12px; font-size:13px; line-height:1.6; color:#cbd5e1;">
                <b>पर्याय १ (याच Render इन्स्टन्सवर - मोफत):</b><br>
                आता सेट केलेले <code>/openclaw/</code> हे स्वतंत्र लिंक थेट लोकल गेटवे रिव्हर्स-प्रॉक्सी करते. एकाच सर्व्हरवर दोन्ही सिस्टीम्स पूर्णपणे वेगळ्या राहतात.
            </div>

            <div class="code-box">
# Install OpenClaw directly from official GitHub source:
git clone https://github.com/openclaw/openclaw.git
cd openclaw && npm install && npm link
openclaw gateway run --port {OPENCLAW_GATEWAY_PORT}
            </div>

            <div style="margin-top:12px; font-size:13px; line-height:1.6; color:#cbd5e1;">
                <b>पर्याय २ (Render Blueprint द्वारे पूर्णपणे स्वतंत्र URL):</b><br>
                Render वर <code>render.yaml</code> मध्ये <code>openclaw-gateway</code> ही स्वतंत्र सेवा समाविष्ट केली आहे. याने तुम्हाला <code>https://openclaw-[नाव].onrender.com</code> हे पूर्णपणे स्वतंत्र डोमेन मिळते!
            </div>
        </div>
    </div>

    <script>
        async function checkStatus() {{
            const log = document.getElementById('portalLog');
            try {{
                const res = await fetch('/openclaw/api/status');
                const data = await res.json();
                log.innerText += '\\n[' + new Date().toLocaleTimeString() + '] Status probe: ' + JSON.stringify(data);
                log.scrollTop = log.scrollHeight;
                if (data.online) {{
                    window.location.reload();
                }}
            }} catch(e) {{
                log.innerText += '\\n[' + new Date().toLocaleTimeString() + '] Error: ' + e.message;
            }}
        }}

        async function startGateway() {{
            const btn = document.getElementById('startBtn');
            const log = document.getElementById('portalLog');
            btn.disabled = true;
            btn.innerText = '⏳ Launching Gateway...';
            try {{
                const res = await fetch('/openclaw/api/start', {{ method: 'POST' }});
                const data = await res.json();
                log.innerText += '\\n[' + new Date().toLocaleTimeString() + '] Launch result: ' + (data.message || 'Done');
                log.scrollTop = log.scrollHeight;
                setTimeout(checkStatus, 2000);
            }} catch(e) {{
                log.innerText += '\\n[' + new Date().toLocaleTimeString() + '] Launch error: ' + e.message;
            }} finally {{
                btn.disabled = false;
                btn.innerText = '⚡ Start OpenClaw Gateway';
            }}
        }}
    </script>
</body>
</html>
"""


def handle_openclaw_route(
    http_handler,
    full_path: str,
    query_params: Optional[Dict[str, Any]] = None,
    body: bytes = b""
) -> bool:
    """
    Handles all requests under `/openclaw` or `/openclaw/*`.
    - If OpenClaw gateway is running on 127.0.0.1:18789, it reverse-proxies the request.
    - If it's an API action (/openclaw/api/status, /openclaw/api/start), it answers via JSON.
    - Otherwise, it renders the OpenClaw dedicated link management page.
    """
    subpath = full_path[len("/openclaw"):].strip()
    if not subpath:
        subpath = "/"

    # 1. API: Status Probe
    if subpath.rstrip("/") == "/api/status":
        online = is_gateway_online(0.3)
        cli_avail, cli_path = is_openclaw_cli_available()
        payload = {
            "success": True,
            "online": online,
            "source": OPENCLAW_REPO_URL,
            "cli_installed": cli_avail,
            "cli_path": cli_path,
            "port": OPENCLAW_GATEWAY_PORT,
            "route": "/openclaw/"
        }
        resp_data = json.dumps(payload).encode("utf-8")
        http_handler.send_response(200)
        http_handler.send_header("Content-Type", "application/json; charset=utf-8")
        http_handler.send_header("Content-Length", str(len(resp_data)))
        http_handler.end_headers()
        http_handler.wfile.write(resp_data)
        return True

    # 2. API: Start Gateway
    if subpath.rstrip("/") == "/api/start":
        res = start_gateway_background(OPENCLAW_GATEWAY_PORT)
        resp_data = json.dumps(res).encode("utf-8")
        http_handler.send_response(200)
        http_handler.send_header("Content-Type", "application/json; charset=utf-8")
        http_handler.send_header("Content-Length", str(len(resp_data)))
        http_handler.end_headers()
        http_handler.wfile.write(resp_data)
        return True

    # 3. Live Reverse-Proxy if Gateway is Online
    if is_gateway_online(0.2):
        try:
            target_url = f"{OPENCLAW_GATEWAY_BASE_URL}{subpath}"
            method = http_handler.command

            # Filter headers
            headers = {}
            for k, v in http_handler.headers.items():
                if k.lower() not in ("host", "content-length"):
                    headers[k] = v

            with httpx.Client(timeout=10.0) as client:
                resp = client.request(
                    method=method,
                    url=target_url,
                    content=body if method in ("POST", "PUT", "PATCH") else None,
                    headers=headers
                )

                http_handler.send_response(resp.status_code)
                for hk, hv in resp.headers.items():
                    if hk.lower() not in ("transfer-encoding", "content-encoding", "connection"):
                        http_handler.send_header(hk, hv)
                http_handler.end_headers()
                http_handler.wfile.write(resp.content)
                return True
        except Exception as proxy_err:
            logger.warning(f"Error reverse-proxying to OpenClaw: {proxy_err}")

    # 4. Default: Render OpenClaw dedicated link portal
    html_content = render_openclaw_portal_html()
    resp_bytes = html_content.encode("utf-8")
    http_handler.send_response(200)
    http_handler.send_header("Content-Type", "text/html; charset=utf-8")
    http_handler.send_header("Content-Length", str(len(resp_bytes)))
    http_handler.end_headers()
    http_handler.wfile.write(resp_bytes)
    return True

