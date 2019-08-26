#!/bin/bash

set -e

THIS_DIR=$( (cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) )

IMAGE_PREFIX=${IMAGE_PREFIX:-dmrub/arvidapp-web}
IMAGE_TAG=${IMAGE_TAG:-latest}
IMAGE_NAME=${IMAGE_PREFIX}:${IMAGE_TAG}

set -e

export LC_ALL=C
unset CDPATH

set -x
docker build -t "${IMAGE_NAME}" \
    -f "$THIS_DIR/Dockerfile.web" \
    "$THIS_DIR"

set +x
echo "Successfully built docker image $IMAGE_NAME"
