#!/bin/bash

echo "=============================="
echo " Raspberry Pi Temperature"
echo "=============================="

TEMP=$(vcgencmd measure_temp)

echo "Current CPU temperature:"
echo "$TEMP"

echo ""
date