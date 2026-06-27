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

# 既存プロセスを停止
pkill -f "$PYTHON.*bus_qt.py" 2>/dev/null
pkill -f "$PYTHON.*bus_server.py" 2>/dev/null
pkill firefox 2>/dev/null
sleep 1

# ネットワーク安定化（eth0 DORMANT / 古いカーネルの TCP スタック対策）
sudo sysctl -w net.ipv4.tcp_keepalive_time=60   2>/dev/null
sudo sysctl -w net.ipv4.tcp_keepalive_intvl=10  2>/dev/null
sudo sysctl -w net.ipv4.tcp_keepalive_probes=3  2>/dev/null
sudo ip link set eth0 up                         2>/dev/null

# スクリーンセーバー・DPMS を無効化（自動スタンバイ防止）
DISPLAY=:0.0 xset s off
DISPLAY=:0.0 xset -dpms

# Qt アプリを起動
DISPLAY=:0.0 $PYTHON "$DIR/bus_qt.py" "$DIR/config.yaml" \
    </dev/null >/tmp/bus_qt.log 2>&1 &
