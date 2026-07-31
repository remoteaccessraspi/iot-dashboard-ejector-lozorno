#!/bin/bash

PORT="/dev/ttyACM0"

echo "================================="
echo "OPTA SOFT RESET"
echo "================================="

echo "Killing serial users..."

fuser -k "$PORT" 2>/dev/null || true

sleep 2

echo "1200 baud touch..."

stty -F "$PORT" 1200

sleep 5

echo "Waiting reconnect..."

for i in {1..15}; do

    if [ -e "$PORT" ]; then
        echo "Opta reconnected"
        exit 0
    fi

    sleep 1
done

echo "ERROR: reconnect timeout"

exit 1