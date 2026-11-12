#!/bin/sh
# Rebuilds dist/morning-newspaper.zip from the morning-newspaper/ skill folder.
set -e
cd "$(dirname "$0")"
rm -f dist/morning-newspaper.zip
mkdir -p dist
zip -qrDX dist/morning-newspaper.zip morning-newspaper -x '*/__pycache__/*' '*.pyc' '*/config.json'
echo "dist/morning-newspaper.zip rebuilt"
