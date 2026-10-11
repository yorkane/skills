#!/usr/bin/env bash
# 起一个带 CDP 调试端口的 Chromium，供 sniff.mjs --cdp 附着。
# 用法: cdp-chrome.sh {start|stop|status} [--port 9222] [--profile DIR] [--headed] [--url URL]
set -uo pipefail

PORT=9222
PROFILE=/data/tmp/vsniff-chrome-profile
HEADED=0
OPEN_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    start|stop|status) ACTION="$1"; shift ;;
    --port) PORT="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --headed) HEADED=1; shift ;;
    --url) OPEN_URL="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done
ACTION=${ACTION:-status}

CHROME_BIN=$(ls -d "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux*/chrome 2>/dev/null | sort -V | tail -1)
PID_FILE=/data/tmp/vsniff-chrome-$PORT.pid
LOG_FILE=/data/tmp/vsniff-chrome-$PORT.log

port_open() {
  curl -s --max-time 2 -o /dev/null -w '%{http_code}' \
    -H 'Upgrade: websocket' -H 'Connection: Upgrade' \
    -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    "http://127.0.0.1:$PORT/devtools/browser" 2>/dev/null | grep -q 101
}

case "$ACTION" in
  start)
    if port_open; then echo "已在运行: http://127.0.0.1:$PORT"; exit 0; fi
    [[ -n "$CHROME_BIN" ]] || { echo "找不到 chromium 可执行文件（~/.cache/ms-playwright）" >&2; exit 1; }
    mkdir -p "$PROFILE"
    HEADLESS_FLAG="--headless=new"
    [[ $HEADED -eq 1 ]] && HEADLESS_FLAG=""
    nohup "$CHROME_BIN" $HEADLESS_FLAG \
      --remote-debugging-port="$PORT" --remote-allow-origins='*' \
      --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check \
      --disable-blink-features=AutomationControlled --disable-dev-shm-usage --no-sandbox \
      --window-size=1280,900 ${OPEN_URL:+"$OPEN_URL"} >"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    for _ in $(seq 1 30); do port_open && break; sleep 1; done
    if port_open; then
      echo "已启动: http://127.0.0.1:$PORT (pid $(cat "$PID_FILE"), profile $PROFILE)"
    else
      echo "启动失败，日志: $LOG_FILE" >&2; tail -20 "$LOG_FILE" >&2; exit 1
    fi
    ;;
  stop)
    if [[ -f "$PID_FILE" ]]; then
      PID=$(cat "$PID_FILE")
      if kill -0 "$PID" 2>/dev/null; then kill "$PID" && echo "已停止 pid $PID"; else echo "进程已不存在"; fi
      rm -f "$PID_FILE"
    else
      echo "没有 pid 文件（$PID_FILE）；如确认要停，先找端口占用: ss -ltnp | grep $PORT" >&2; exit 1
    fi
    ;;
  status)
    if port_open; then
      echo "可用: http://127.0.0.1:$PORT (pid ${PID_FILE:+$(cat "$PID_FILE" 2>/dev/null)})"
      curl -s "http://127.0.0.1:$PORT/json/version" | head -c 300; echo
    else
      echo "不可用: 端口 $PORT 上没有 CDP 端点"
    fi
    ;;
esac

