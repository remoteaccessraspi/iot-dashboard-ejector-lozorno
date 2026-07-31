#!/bin/bash

echo "Restarting IOT system..."

sudo systemctl restart iot-master
sudo systemctl restart relay-engine
sudo systemctl restart iot-dashboard

echo "DONE"

