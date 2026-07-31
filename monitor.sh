#!/bin/bash

PORT="/dev/ttyACM0"
BAUD=115200

RUNNING=1

# zachytenie Ctrl+C
trap "echo 'Ukončujem...'; RUNNING=0; exit 0" SIGINT SIGTERM

echo "=============================="
echo "Arduino CLI Monitor"
echo "=============================="

if [ ! -e "$PORT" ]; then
    PORT=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)
fi

if [ -z "$PORT" ]; then
    echo "ERROR: Arduino nenájdené"
    exit 1
fi

echo "PORT: $PORT"
echo "BAUD: $BAUD"

fuser -k $PORT 2>/dev/null
sleep 1

while [ $RUNNING -eq 1 ]; do

    arduino-cli monitor -p "$PORT" -c baudrate="$BAUD"

    # ak user dal Ctrl+C → skonči
    if [ $RUNNING -eq 0 ]; then
        break
    fi

    echo ""
    echo "Reconnect..."
    sleep 1

    PORT=$(ls /dev/ttyACM* 2>/dev/null | head -n 1)
done