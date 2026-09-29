#!/bin/sh
set -eu

MODEL_DIR=/opt/sentinel/models
SENTINEL_LLM_MODEL="${SENTINEL_LLM_MODEL:-Qwen3-4B-Instruct-2507}"
SENTINEL_LLAMA_CPP_PORT="${SENTINEL_LLAMA_CPP_PORT:-8888}"
export SENTINEL_LLAMA_CPP_PORT

case "$SENTINEL_LLAMA_CPP_PORT" in
  ''|*[!0-9]*)
    echo "SENTINEL_LLAMA_CPP_PORT must be an integer from 1 to 65535, got ${SENTINEL_LLAMA_CPP_PORT}" >&2
    exit 1
    ;;
esac
if [ "$SENTINEL_LLAMA_CPP_PORT" -lt 1 ] || [ "$SENTINEL_LLAMA_CPP_PORT" -gt 65535 ]; then
  echo "SENTINEL_LLAMA_CPP_PORT must be an integer from 1 to 65535, got ${SENTINEL_LLAMA_CPP_PORT}" >&2
  exit 1
fi

gguf=""
count=0
for f in "$MODEL_DIR"/*.gguf; do
  [ -f "$f" ] || continue
  count=$((count + 1))
  gguf=$f
done

if [ "$count" -eq 0 ]; then
  echo "No GGUF found in $MODEL_DIR" >&2
  exit 1
fi
if [ "$count" -gt 1 ]; then
  echo "Expected exactly one GGUF in $MODEL_DIR, found $count:" >&2
  ls -1 "$MODEL_DIR"/*.gguf >&2
  exit 1
fi

llama serve \
  -m "$gguf" \
  -a "$SENTINEL_LLM_MODEL" \
  --host 127.0.0.1 --port "$SENTINEL_LLAMA_CPP_PORT" \
  --jinja --reasoning off \
  -c 8192 \
  -n 1024 \
  -np 1 \
  --no-webui \
  >/var/log/llama-server.log 2>&1 &
llama_pid=$!

cleanup() {
  kill "$llama_pid" 2>/dev/null || true
  wait "$llama_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

i=0
while [ "$i" -lt 180 ]; do
  if ! kill -0 "$llama_pid" 2>/dev/null; then
    echo "llama-server exited before becoming ready" >&2
    tail -n 50 /var/log/llama-server.log >&2 || true
    exit 1
  fi
  if python3 -c 'import os, urllib.request; urllib.request.urlopen("http://127.0.0.1:%s/health" % os.environ["SENTINEL_LLAMA_CPP_PORT"], timeout=2)' \
      >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 1
done

if [ "$i" -ge 180 ]; then
  echo "Timed out waiting for llama-server on 127.0.0.1:${SENTINEL_LLAMA_CPP_PORT}" >&2
  tail -n 50 /var/log/llama-server.log >&2 || true
  exit 1
fi

sentinel "$@"
