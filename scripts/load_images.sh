#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="${ROOT_DIR}/release"

docker load -i "${RELEASE_DIR}/backend-image.tar"
docker load -i "${RELEASE_DIR}/gateway-image.tar"

echo "镜像导入完成"
