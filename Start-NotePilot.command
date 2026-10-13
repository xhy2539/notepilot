#!/bin/bash
# Finder: right-click > Open, or run bash scripts/start-mac.sh in Terminal.
TASK_ROOT="$(cd "$(dirname "$0")" && pwd)"
exec bash "$TASK_ROOT/scripts/start-mac.sh" "$@"
