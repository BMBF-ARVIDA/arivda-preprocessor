#!/bin/bash

THIS_DIR=$( (cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) )

IMAGE_PREFIX=${IMAGE_PREFIX:-dmrub/arvidapp-web}
IMAGE_TAG=${IMAGE_TAG:-latest}
IMAGE_NAME=${IMAGE_PREFIX}:${IMAGE_TAG}

cd "$THIS_DIR"
ARGS=()

set -xe
docker run -p 8080:8080 "${ARGS[@]}" \
       --name=arvidapp-web \
       --rm -ti "${IMAGE_NAME}" \
       --log-to-console \
       --debug \
       --port 8080 \
        "$@"
