#!/usr/bin/env bash
# Re-generate package-lock.json for reproducible podman builds.
# Run this on a machine that can reach https://registry.npmjs.org (e.g. RHEL host with podman).
set -euo pipefail
cd "$(dirname "$0")"

# Use a throwaway container so the host doesn't need Node installed.
podman run --rm -v "$PWD":/app:Z -w /app docker.io/library/node:20-alpine \
  sh -c "npm install --package-lock-only --no-audit --no-fund"

echo "package-lock.json generated."
