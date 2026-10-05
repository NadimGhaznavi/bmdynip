#!/usr/bin/env bash
# Reuse installation while retaining configuration, saved state, and credentials.
set -euo pipefail
if [[ $# == 1 && $1 == --help ]]; then
    printf 'Usage: sudo scripts/upgrade.sh\nDeploy BMDynIP, retaining configuration, saved state, and credentials; restart the Web UI.\n'
    exit 0
fi
if [[ $# != 0 ]]; then
    printf 'Usage: sudo scripts/upgrade.sh\n' >&2
    exit 1
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
exec ./scripts/install.sh
