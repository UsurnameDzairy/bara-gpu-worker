#!/usr/bin/env bash
set -euo pipefail

if [ ! -d /runpod-volume ]; then
    echo "bara-gpu-worker: /runpod-volume is missing. Attach the network volume to this endpoint, the weights (18 GB) are stored there." >&2
    exit 1
fi

python /src/ensure_weights.py /weights.json /runpod-volume/models

# Hand over to the base image's own start command (its CMD is ["/start.sh"]).
exec /start.sh
