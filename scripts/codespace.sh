#!/usr/bin/env bash
# Bootstrap the one-node classroom demo in its own Codespace.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
: "${CODESPACE_NAME:?Run this helper in the DroneLog Codespace.}"
for attempt in {1..30}; do
  if docker info >/dev/null 2>&1; then break; fi
  sleep 2
done
docker info >/dev/null
if ! docker container inspect dronelog-registry >/dev/null 2>&1; then
  docker run -d --restart unless-stopped --name dronelog-registry \
    -p 127.0.0.1:5000:5000 registry:2.8.3
else
  docker start dronelog-registry >/dev/null
fi
for attempt in {1..15}; do
  if curl -fsS http://127.0.0.1:5000/v2/ >/dev/null; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:5000/v2/
if [[ "$(docker info --format '{{.Swarm.LocalNodeState}}')" == inactive ]]; then
  docker swarm init --advertise-addr eth0 --data-path-port 7789 >/dev/null
fi
bash scripts/deploy.sh localhost:5000 "demo-$(git rev-parse --short=12 HEAD)"
