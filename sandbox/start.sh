#!/bin/sh
set -eu
# CDP is private to the sandbox network; never publish this port publicly.
# Chromium's nested user namespaces are unavailable in the container runtime.
# Isolation is provided by the per-workflow container and its egress policy;
# do not run this image privileged or mount host application data into it.
chromium --headless=new --no-sandbox --remote-debugging-port=9223 --remote-debugging-address=127.0.0.1 \
  --user-data-dir=/home/browser/profile --no-first-run --no-default-browser-check \
  --disable-dev-shm-usage about:blank &
chrome_pid=$!
socat TCP-LISTEN:9222,bind=0.0.0.0,fork,reuseaddr TCP:127.0.0.1:9223 &
proxy_pid=$!
trap 'kill "$chrome_pid" "$proxy_pid" 2>/dev/null || true' EXIT INT TERM
wait "$chrome_pid"
