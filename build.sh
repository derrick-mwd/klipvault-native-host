#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VERSION=$(grep '"version"' manifest.json | head -1 | sed 's/.*"version": "\([^"]*\)".*/\1/')
echo "Building KlipVault Extension v$VERSION"

# --- Chrome build ---
rm -f "klipvault-extension-chrome-v$VERSION.zip"
zip -r "klipvault-extension-chrome-v$VERSION.zip" \
  manifest.json \
  background.js \
  content.js \
  popup.html \
  popup.css \
  popup.js \
  icons/ \
  README.md \
  -x "*/.*" -x "*.zip" -x "build.sh"

# --- Firefox build ---
# Firefox requires manifest.json (not manifest-firefox.json) inside the zip
rm -rf .firefox-build
mkdir -p .firefox-build
cp manifest-firefox.json .firefox-build/manifest.json
cp background.js content.js popup.html popup.css popup.js .firefox-build/
cp -r icons .firefox-build/
cp README.md .firefox-build/

rm -f "klipvault-extension-firefox-v$VERSION.zip"
cd .firefox-build
zip -r "../klipvault-extension-firefox-v$VERSION.zip" \
  manifest.json \
  background.js \
  content.js \
  popup.html \
  popup.css \
  popup.js \
  icons/ \
  README.md

cd ..
rm -rf .firefox-build

echo ""
echo "Built:"
echo "  - klipvault-extension-chrome-v$VERSION.zip"
echo "  - klipvault-extension-firefox-v$VERSION.zip"
echo ""
echo "Chrome: Load unpacked or drag .zip to chrome://extensions/"
echo "Firefox: about:debugging > This Firefox > Load Temporary Add-on > select .zip"
