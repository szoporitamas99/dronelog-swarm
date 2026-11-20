#!/usr/bin/env bash
# Standard-library Python implementation of the same checks as test.ps1.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
exec python3 scripts/swarm_test.py "$@"
