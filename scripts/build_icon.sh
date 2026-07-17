#!/bin/bash
# build_icon.sh — render scripts/icon.html to a 1024px PNG, pack it into an
# .icns, and install it into ~/Applications/Bahasa Player.app.
#
# The app is an osacompile'd AppleScript applet, whose Info.plist points at
# CFBundleIconFile "applet" — so the icon lives at Contents/Resources/applet.icns.
# osacompile ad-hoc signs the bundle, and swapping a resource invalidates that
# signature, so we re-sign afterwards or macOS may refuse to launch it.
#
# Usage: ./scripts/build_icon.sh
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
app="$HOME/Applications/Bahasa Player.app"
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

[ -x "$chrome" ] || { echo "✗ Google Chrome not found at $chrome" >&2; exit 1; }

# 1. Render the art to a transparent 1024x1024 PNG.
"$chrome" --headless --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 \
  --default-background-color=00000000 \
  --window-size=1024,1024 \
  --screenshot="$work/icon.png" \
  "file://$here/icon.html" >/dev/null 2>&1

[ -f "$work/icon.png" ] || { echo "✗ Chrome produced no screenshot" >&2; exit 1; }
cp "$work/icon.png" "$root/icon-1024.png"

# 2. Build the iconset at every size macOS asks for.
set -- 16 icon_16x16 32 icon_16x16@2x 32 icon_32x32 64 icon_32x32@2x \
       128 icon_128x128 256 icon_128x128@2x 256 icon_256x256 512 icon_256x256@2x \
       512 icon_512x512 1024 icon_512x512@2x
iconset="$work/icon.iconset"
mkdir -p "$iconset"
while [ $# -gt 0 ]; do
  sips -z "$1" "$1" "$work/icon.png" --out "$iconset/$2.png" >/dev/null
  shift 2
done

iconutil -c icns "$iconset" -o "$root/icon.icns"

# 3. Install into the app bundle and re-sign.
if [ -d "$app" ]; then
  cp "$root/icon.icns" "$app/Contents/Resources/applet.icns"
  touch "$app"                                    # nudge Finder/LaunchServices
  codesign --force --sign - "$app" >/dev/null 2>&1 || true
  echo "✅ icon installed into $app"
else
  echo "⚠️  $app not found — built icon.icns only (rebuild the app, then re-run)"
fi

echo "   art:  $root/icon-1024.png"
echo "   icns: $root/icon.icns"
