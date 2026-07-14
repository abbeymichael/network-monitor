#!/usr/bin/env bash
#
# Build the PingSentry installable/executable on macOS or Linux.
#
# Usage:
#   ./build.sh
#
# Output:
#   dist/PingSentry            (Linux single-file executable)
#   dist/PingSentry.app        (macOS application bundle)
#
set -euo pipefail

cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "==> Using interpreter: $($PY --version 2>&1)"

# 1. Ensure build/runtime dependencies are present.
echo "==> Installing dependencies (requirements.txt + pyinstaller)"
"$PY" -m pip install --upgrade pip >/dev/null
"$PY" -m pip install -r requirements.txt

# 2. Clean previous artifacts.
echo "==> Cleaning previous build artifacts"
rm -rf build dist

# 3. Build with the bundled spec (bundles on.wav / off.wav, windowed).
echo "==> Building with PyInstaller"
"$PY" -m PyInstaller --clean --noconfirm PingSentry.spec

echo ""
echo "==> Build complete. Artifacts in ./dist :"
ls -lh dist || true

case "$(uname -s)" in
    Darwin)
        echo ""
        echo "macOS app bundle: dist/PingSentry.app"
        echo "To create a distributable DMG, run:  ./build.sh && hdiutil create -volname PingSentry -srcfolder dist/PingSentry.app -ov -format UDZO dist/PingSentry.dmg"
        ;;
    Linux)
        echo ""
        echo "Linux executable: dist/PingSentry  (run it directly)"
        ;;
esac
