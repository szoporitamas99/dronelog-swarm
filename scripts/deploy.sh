#!/usr/bin/env bash
# Linux/macOS Bash alternative. Windows users should use deploy.ps1 instead.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

DOCKERHUB_USER="${1:-}"
APP_TAG="${2:-1.0.0}"
if [[ "$DOCKERHUB_USER" != 'localhost:5000' && ! "$DOCKERHUB_USER" =~ ^[a-z0-9][a-z0-9_-]{2,}$ ]]; then
  printf 'Usage: bash scripts/deploy.sh DOCKER_HUB_USER_OR_localhost:5000 [1.0.0]\n' >&2
  exit 2
fi
if [[ ! "$APP_TAG" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
  printf 'Invalid Docker image tag.\n' >&2
  exit 2
fi
[[ "$APP_TAG" != 'latest' ]] || { printf 'Use a fixed version tag such as 1.0.0.\n' >&2; exit 2; }
command -v docker >/dev/null || { printf 'Install and start Docker Engine first.\n' >&2; exit 1; }
command -v python3 >/dev/null || { printf 'Python 3 is required by the Bash helper.\n' >&2; exit 1; }
[[ "$(docker info --format '{{.OSType}}')" == 'linux' ]] || { printf 'Linux containers are required.\n' >&2; exit 1; }

swarm_state="$(docker info --format '{{.Swarm.LocalNodeState}}')"
if [[ "$swarm_state" == 'inactive' ]]; then
  docker swarm init >/dev/null
elif [[ "$swarm_state" != 'active' ]]; then
  printf 'Resolve the existing Swarm state (%s); this script will not reset it.\n' "$swarm_state" >&2
  exit 1
fi
[[ "$(docker info --format '{{.Swarm.ControlAvailable}}')" == 'true' ]] || { printf 'Run this script against a Swarm manager.\n' >&2; exit 1; }
node_id="$(docker info --format '{{.Swarm.NodeID}}')"
node_ids="$(docker node ls --format '{{.ID}}')"
# Docker node IDs contain no spaces or shell metacharacters.
# shellcheck disable=SC2086
other_db_nodes="$(docker node inspect $node_ids | python3 -c 'import json,sys; current=sys.argv[1]; print(" ".join(n["ID"] for n in json.load(sys.stdin) if (n["Spec"].get("Labels") or {}).get("dronelog.db")=="true" and n["ID"]!=current))' "$node_id")"
[[ -z "$other_db_nodes" ]] || { printf 'Another node owns the database label. Deploy on the original database node.\n' >&2; exit 1; }
docker node update --label-add dronelog.db=true "$node_id"
docker volume create --label project=dronelog dronelog_pgdata

umask 077
mkdir -p .secrets
chmod 700 .secrets
for secret_short in db_password admin_token; do
  secret_name="dronelog_${secret_short}"
  secret_file=".secrets/${secret_short}.txt"
  secret_exists=false
  if docker secret inspect "$secret_name" >/dev/null 2>&1; then secret_exists=true; fi
  if [[ "$secret_exists" == 'true' && ! -f "$secret_file" ]]; then
    printf 'Secret %s exists, but its local file is missing. Restore the original .secrets folder.\n' "$secret_name" >&2
    exit 1
  fi
  if [[ ! -f "$secret_file" ]]; then
    python3 - "$secret_file" <<'PY'
import pathlib, secrets, sys
pathlib.Path(sys.argv[1]).write_text(secrets.token_hex(32), encoding="utf-8")
PY
  fi
  chmod 600 "$secret_file"
  local_hash="$(python3 -c 'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$secret_file")"
  if [[ "$secret_exists" == 'true' ]]; then
    remote_hash="$(docker secret inspect --format '{{json .Spec.Labels}}' "$secret_name" | python3 -c 'import json,sys; print((json.load(sys.stdin) or {}).get("dronelog.sha256", ""))')"
    if [[ -z "$remote_hash" ]]; then
      printf 'Cannot verify existing secret %s: fingerprint label is absent. This script will not overwrite unknown secrets.\n' "$secret_name" >&2
      exit 1
    fi
    if [[ -n "$remote_hash" && "$remote_hash" != "$local_hash" ]]; then
      printf 'Local secret file mismatch: %s. Restore the original file.\n' "$secret_name" >&2
      exit 1
    fi
    printf 'Reusing existing secret: %s\n' "$secret_name"
  else
    docker secret create --label "dronelog.sha256=$local_hash" "$secret_name" "$secret_file"
  fi
done

export DOCKERHUB_USER APP_TAG
printf 'Building and pushing application images to %s.\n' "$DOCKERHUB_USER"
for component in backend frontend; do
  image_name="${DOCKERHUB_USER}/dronelog-${component}:${APP_TAG}"
  docker build --pull --tag "$image_name" "./$component"
  docker push "$image_name"
done
docker stack config --compose-file stack.yml
docker stack deploy --with-registry-auth --resolve-image always --compose-file stack.yml dronelog
python3 scripts/swarm_test.py --wait-ready
docker stack services dronelog
docker stack ps --no-trunc dronelog
printf 'Ready: http://localhost:8080\nAdmin token: cat .secrets/admin_token.txt (keep private).\nNext: bash scripts/test.sh\n'
