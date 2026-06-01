#!/usr/bin/env bash
#
# Setup script for WeChat Desktop scraper.
# Creates a venv, installs dependencies, and runs a sanity check.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== WeChat Desktop Scraper — Setup ==="
echo ""

# 1. Create virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "[✓] Virtual environment already exists at .venv/"
else
    echo "[1/4] Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "  Created .venv/"
fi

# Activate
source "$VENV_DIR/bin/activate"
echo "  Using Python: $(python --version) at $(which python)"
echo ""

# 2. Install PaddlePaddle
echo "[2/4] Installing PaddlePaddle..."
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    echo "  Detected Apple Silicon — installing CPU version for arm64"
    pip install --quiet paddlepaddle==0.0.0 \
        -f https://www.paddlepaddle.org.cn/whl/mac/cpu/develop.html 2>/dev/null || \
    pip install --quiet paddlepaddle
else
    echo "  Detected Intel Mac — installing CPU version"
    pip install --quiet paddlepaddle
fi
echo ""

# 3. Install remaining dependencies
echo "[3/4] Installing dependencies..."
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "  Installed: paddleocr, pyautogui, pyobjc, opencv-python, Pillow"
echo ""

# 4. Sanity check
echo "[4/4] Running sanity checks..."
python -c "
import sys

errors = []

try:
    from paddleocr import PaddleOCR
    print('  [✓] PaddleOCR imports OK')
except ImportError as e:
    errors.append(f'PaddleOCR: {e}')
    print(f'  [✗] PaddleOCR: {e}')

try:
    import pyautogui
    print('  [✓] pyautogui imports OK')
except ImportError as e:
    errors.append(f'pyautogui: {e}')
    print(f'  [✗] pyautogui: {e}')

try:
    import Quartz
    from AppKit import NSWorkspace
    print('  [✓] pyobjc (Quartz + AppKit) imports OK')
except ImportError as e:
    errors.append(f'pyobjc: {e}')
    print(f'  [✗] pyobjc: {e}')

try:
    import cv2
    print('  [✓] opencv-python imports OK')
except ImportError as e:
    errors.append(f'opencv: {e}')
    print(f'  [✗] opencv: {e}')

try:
    from PIL import ImageGrab
    print('  [✓] Pillow imports OK')
except ImportError as e:
    errors.append(f'Pillow: {e}')
    print(f'  [✗] Pillow: {e}')

# Check WeChat
try:
    from AppKit import NSWorkspace
    workspace = NSWorkspace.sharedWorkspace()
    wechat_running = any(
        app.bundleIdentifier() == 'com.tencent.xinWeChat'
        for app in workspace.runningApplications()
    )
    if wechat_running:
        print('  [✓] WeChat Desktop is running')
    else:
        print('  [!] WeChat Desktop is NOT running — start it before scraping')
except Exception:
    print('  [!] Could not check WeChat status')

if errors:
    print(f'\n  {len(errors)} import(s) failed. Fix above errors before running.')
    sys.exit(1)
"

echo ""
echo "=== Setup complete ==="
echo ""
echo "IMPORTANT: Grant Accessibility permissions for your terminal app:"
echo "  System Settings → Privacy & Security → Accessibility"
echo "  Add: Terminal.app (or iTerm, VS Code, etc.)"
echo ""
echo "To run the scraper:"
echo "  source .venv/bin/activate"
echo "  python scraper.py"
echo ""
