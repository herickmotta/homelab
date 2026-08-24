#!/usr/bin/env bash
# Export generic YOLOv9-small 320x320 ONNX for Frigate OpenVINO.
# Run on a workstation with Docker BuildKit. Do not commit the ONNX file.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${OUT_DIR:-${ROOT}/.cache/frigate-models}"
OUT_FILE="${OUT_DIR}/yolov9-s-320.onnx"
MODEL_SIZE="${MODEL_SIZE:-s}"
IMG_SIZE="${IMG_SIZE:-320}"
UV_IMAGE="${UV_IMAGE:-ghcr.io/astral-sh/uv:0.8.0}"
ONNX_VERSION="${ONNX_VERSION:-1.18.0}"
ONNX_SIMPLIFIER="${ONNX_SIMPLIFIER:-0.4.36}"

if command -v sha256sum >/dev/null 2>&1; then
  hash_file() { sha256sum "$1"; }
else
  hash_file() { shasum -a 256 "$1"; }
fi

mkdir -p "${OUT_DIR}"

if [[ -f "${OUT_FILE}" ]]; then
  echo "exists ${OUT_FILE}"
  hash_file "${OUT_FILE}"
  exit 0
fi

export DOCKER_BUILDKIT=1

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT
cd "${WORKDIR}"

docker build \
  --build-arg MODEL_SIZE="${MODEL_SIZE}" \
  --build-arg IMG_SIZE="${IMG_SIZE}" \
  --build-arg UV_IMAGE="${UV_IMAGE}" \
  --build-arg ONNX_VERSION="${ONNX_VERSION}" \
  --build-arg ONNX_SIMPLIFIER="${ONNX_SIMPLIFIER}" \
  --output "${OUT_DIR}" \
  -f- . <<'EOF'
FROM python:3.11 AS build
ARG UV_IMAGE
ARG ONNX_VERSION
ARG ONNX_SIMPLIFIER
ARG MODEL_SIZE
ARG IMG_SIZE
RUN apt-get update \
  && apt-get install --no-install-recommends -y cmake libgl1 git \
  && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /bin/uv
WORKDIR /yolov9
ADD https://github.com/WongKinYiu/yolov9.git .
RUN uv pip install --system -r requirements.txt \
  && uv pip install --system \
    "onnx==${ONNX_VERSION}" \
    onnxruntime \
    "onnxsim==${ONNX_SIMPLIFIER}" \
    onnxscript
ADD https://github.com/WongKinYiu/yolov9/releases/download/v0.1/yolov9-${MODEL_SIZE}-converted.pt \
  yolov9-${MODEL_SIZE}.pt
RUN sed -i "s/ckpt = torch.load(attempt_download(w), map_location='cpu')/ckpt = torch.load(attempt_download(w), map_location='cpu', weights_only=False)/g" \
    models/experimental.py
RUN python3 export.py \
  --weights "./yolov9-${MODEL_SIZE}.pt" \
  --imgsz "${IMG_SIZE}" \
  --simplify \
  --include onnx \
  --opset 12
FROM scratch
ARG MODEL_SIZE
ARG IMG_SIZE
COPY --from=build /yolov9/yolov9-${MODEL_SIZE}.onnx /yolov9-${MODEL_SIZE}-${IMG_SIZE}.onnx
EOF

if [[ -f "${OUT_DIR}/yolov9-${MODEL_SIZE}-${IMG_SIZE}.onnx" && ! -f "${OUT_FILE}" ]]; then
  mv "${OUT_DIR}/yolov9-${MODEL_SIZE}-${IMG_SIZE}.onnx" "${OUT_FILE}"
fi

test -f "${OUT_FILE}"
hash_file "${OUT_FILE}" | tee "${OUT_FILE}.sha256"
echo "YOLOv9s-320 ONNX written to ${OUT_FILE}"
echo "Copy it onto the Frigate guest and set frigate_model=yolov9s320."
