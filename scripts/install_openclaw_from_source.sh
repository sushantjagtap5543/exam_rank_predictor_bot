#!/usr/bin/env bash
# ==============================================================================
# ExamRankers — Isolated OpenClaw Gateway Installer & Service Daemon
# Official Source: https://github.com/openclaw/openclaw.git
# ==============================================================================
set -e

PORT=${OPENCLAW_GATEWAY_PORT:-18789}
TARGET_DIR="${OPENCLAW_INSTALL_DIR:-$HOME/openclaw_service}"

echo "======================================================================"
echo "🦞 Installing OpenClaw Gateway from Official Source:"
echo "   URL: https://github.com/openclaw/openclaw.git"
echo "   Gateway Port: ${PORT}"
echo "   Target Directory: ${TARGET_DIR}"
echo "======================================================================"

mkdir -p "$TARGET_DIR"

if [ ! -d "$TARGET_DIR/.git" ]; then
    echo "⬇️ Cloning official OpenClaw repository..."
    git clone --depth 1 https://github.com/openclaw/openclaw.git "$TARGET_DIR"
else
    echo "🔄 Existing repository found, pulling latest official updates..."
    cd "$TARGET_DIR" && git pull origin main || true
fi

cd "$TARGET_DIR"

# Check if Node.js & npm/pnpm exist
if command -v npm >/dev/null 2>&1; then
    echo "📦 Installing OpenClaw dependencies..."
    npm install --omit=dev --no-audit || pnpm install --prod || true
fi

echo "======================================================================"
echo "🚀 Starting OpenClaw Gateway on port ${PORT}..."
echo "   Separate Reverse-Proxy Link: /openclaw/"
echo "   Local Binding: http://127.0.0.1:${PORT}"
echo "======================================================================"

if command -v openclaw >/dev/null 2>&1; then
    exec openclaw gateway run --port "$PORT"
else
    # Fallback to local package execution
    exec node bin/openclaw.js gateway run --port "$PORT" || npx openclaw gateway run --port "$PORT"
fi
