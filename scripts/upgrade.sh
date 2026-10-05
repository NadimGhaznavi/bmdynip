#!/usr/bin/env bash
# Reuse installation while retaining configuration, saved state, and credentials.
set -euo pipefail
if [[ $# == 1 && $1 == --help ]]; then
    printf 'Usage: sudo scripts/upgrade.sh\nStop the Web UI, deploy BMDynIP retaining configuration, saved state, and credentials, then start the Web UI.\n'
    exit 0
fi
if [[ $# != 0 ]]; then
    printf 'Usage: sudo scripts/upgrade.sh\n' >&2
    exit 1
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
exec /usr/bin/python3 scripts/install.py upgrade
