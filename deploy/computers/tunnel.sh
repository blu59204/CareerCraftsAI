#!/bin/sh
set -eu
cp /secrets/sandbox.key /tmp/sandbox.key
chmod 600 /tmp/sandbox.key
exec ssh -N -T -i /tmp/sandbox.key -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/secrets/known_hosts \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=20 -o ServerAliveCountMax=3 \
  -L 0.0.0.0:14312:127.0.0.1:14312 ubuntu@129.154.38.17
