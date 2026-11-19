#!/bin/bash
# Phase 1 attempt 2 (D023): all runs from the same frozen commit.
set -o pipefail
cd "$(dirname "$0")/.."
run() { echo "=== $* $(date -u +%T)"; uv run longshot "$@" 2>&1 | grep -v UV_NATIVE; return ${PIPESTATUS[0]}; }
run search --config configs/calib_normal.yaml || { echo "FAILED calib_normal"; exit 1; }
run search --config configs/calib_inverted.yaml || { echo "FAILED calib_inverted"; exit 1; }
run inject --config configs/inject_calib.yaml || { echo "FAILED inject"; exit 1; }
run validate --config configs/validate_phase1.yaml || { echo "FAILED validate"; exit 1; }
echo "ALL DONE $(date -u +%T)"
