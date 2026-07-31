#!/bin/bash
set -e

echo "=============================="
echo " IOT DASHBOARD GIT PULL"
echo "=============================="

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo ""
echo "Pulling from origin/main (rebase)..."
git pull --rebase origin main

echo "DONE"
