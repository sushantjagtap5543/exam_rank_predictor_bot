#!/data/data/com.termux/files/usr/bin/bash
# ====================================================================
# ExamRankers India Bot — 24/7 Termux Host Script (Android Phone)
# ====================================================================
# Runs your bot 24/7 on any spare Android phone with ZERO cloud costs!
#
# Steps:
# 1. Install Termux from F-Droid (free).
# 2. Open Termux and run: bash termux_setup.sh
# ====================================================================

echo "🚀 [1/4] Updating Termux packages..."
pkg update -y && pkg upgrade -y

echo "📦 [2/4] Installing Python and required system libraries..."
pkg install -y python git termux-tools clang freetype libjpeg-turbo libpng

echo "🔋 [3/4] Acquiring Termux Wake-Lock (Keeps bot running 24/7 even with screen locked)..."
termux-wake-lock

echo "📚 [4/4] Installing Python requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "===================================================="
echo "✅ Setup Complete! Starting ExamRankers Bot 24/7..."
echo "===================================================="
python -m app.bot
