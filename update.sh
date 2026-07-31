#!/usr/bin/env bash
set -e

echo "Updating repository..."
git pull

echo "Activating venv..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Restarting services..."
sudo systemctl restart iot-master
sudo systemctl restart iot-converter
sudo systemctl restart iot-dashboard

echo "Update complete."
