# ==============================================================================
# ExamRankers — Isolated OpenClaw Gateway Installer & Service Daemon (Windows)
# Official Source: https://github.com/openclaw/openclaw.git
# ==============================================================================
$ErrorActionPreference = "Stop"

$Port = if ($env:OPENCLAW_GATEWAY_PORT) { $env:OPENCLAW_GATEWAY_PORT } else { "18789" }
$TargetDir = if ($env:OPENCLAW_INSTALL_DIR) { $env:OPENCLAW_INSTALL_DIR } else { "$HOME\openclaw_service" }

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "🦞 Installing OpenClaw Gateway from Official Source:" -ForegroundColor Yellow
Write-Host "   URL: https://github.com/openclaw/openclaw.git" -ForegroundColor White
Write-Host "   Gateway Port: $Port" -ForegroundColor White
Write-Host "   Target Directory: $TargetDir" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Cyan

if (-not (Test-Path "$TargetDir")) {
    New-Item -ItemType Directory -Path "$TargetDir" -Force | Out-Null
}

if (-not (Test-Path "$TargetDir\.git")) {
    Write-Host "⬇️ Cloning official OpenClaw repository..." -ForegroundColor Yellow
    git clone --depth 1 https://github.com/openclaw/openclaw.git "$TargetDir"
} else {
    Write-Host "🔄 Existing repository found, pulling latest official updates..." -ForegroundColor Green
    Set-Location "$TargetDir"
    git pull origin main
}

Set-Location "$TargetDir"

if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "📦 Installing OpenClaw dependencies..." -ForegroundColor Yellow
    npm install --omit=dev --no-audit
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "🚀 Starting OpenClaw Gateway on port $Port..." -ForegroundColor Green
Write-Host "   Separate Reverse-Proxy Link: /openclaw/" -ForegroundColor White
Write-Host "   Local Binding: http://127.0.0.1:$Port" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Cyan

if (Get-Command openclaw -ErrorAction SilentlyContinue) {
    & openclaw gateway run --port $Port
} else {
    & npx openclaw gateway run --port $Port
}
