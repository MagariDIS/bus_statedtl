#!/bin/bash
DIR=/home/marek/python_apps/bus_statedtl

# Python コマンドの検出
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    PYTHON=python2
fi

# 既存プロセスを停止（不要なタブを残さないよう Firefox も終了）
pkill -f "$PYTHON.*bus_server.py" 2>/dev/null
pkill firefox 2>/dev/null
sleep 1

# サーバーをバックグラウンドで起動
$PYTHON "$DIR/bus_server.py" "$DIR/config.yaml" 8080 \
    </dev/null >/tmp/bus_server.log 2>&1 &

# Firefox を起動
sleep 2
DISPLAY=:0.0 firefox http://localhost:8080/ &
