#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="${ROOT_DIR}/release"
APP_IMAGE="${APP_IMAGE:-huawei-inspection-backend:latest}"
GATEWAY_IMAGE="${GATEWAY_IMAGE:-huawei-inspection-gateway:latest}"

mkdir -p "${RELEASE_DIR}"

docker image inspect "${APP_IMAGE}" >/dev/null
docker image inspect "${GATEWAY_IMAGE}" >/dev/null

docker save -o "${RELEASE_DIR}/backend-image.tar" "${APP_IMAGE}"
docker save -o "${RELEASE_DIR}/gateway-image.tar" "${GATEWAY_IMAGE}"

cp "${ROOT_DIR}/docker-compose.yml" "${RELEASE_DIR}/docker-compose.yml"
cp "${ROOT_DIR}/docker-compose.override-config.yml" "${RELEASE_DIR}/docker-compose.override-config.yml"
cp "${ROOT_DIR}/docker-compose.override-templates.yml" "${RELEASE_DIR}/docker-compose.override-templates.yml"
cp "${ROOT_DIR}/.env.example" "${RELEASE_DIR}/.env.example"

echo "导出完成：${RELEASE_DIR}"
