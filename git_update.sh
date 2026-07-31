#!/bin/bash
set -e

echo "=============================="
echo " IOT DASHBOARD GIT UPDATE"
echo "=============================="

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo ""
echo "Adding files..."
git add .

if git diff --cached --quiet; then
    echo "No changes to commit."
    exit 0
fi

TS=$(date "+%Y-%m-%d %H:%M:%S")

echo "Commit: $TS"
git commit -m "update $TS"

echo "Syncing with remote (rebase)..."
git pull --rebase origin main

echo "Pushing to GitHub..."
git push origin main

echo "DONE"
