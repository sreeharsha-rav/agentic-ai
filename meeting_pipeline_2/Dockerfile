# Deployment scaffold -- NOT yet tuned/validated. Adjust once a stage is
# actually implemented (in particular: pin an OCR backend extra below once
# one is chosen, and consider a GPU base image if `device="cuda"` is used
# for Whisper/embeddings).

FROM python:3.12-slim AS base

# ffmpeg is a hard runtime requirement of the TRANSCRIBE stage (see
# src/meeting_pipeline_2/media/ffmpeg_runner.py) -- it is a system package,
# not a pip dependency, so it must be installed at the image level.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies before copying source so this layer is cache-friendly
# across source-only changes.
COPY pyproject.toml README.md ./
COPY src ./src

# TODO: pick one OCR extra once a backend is decided for production
# (rapidocr recommended default -- see docs from ../meeting_pipeline/docs/ocr_backends.md):
#   RUN pip install --no-cache-dir ".[ocr]"
RUN pip install --no-cache-dir .

# Pipeline artifacts are written here; mount a volume in production so
# outputs survive container restarts.
VOLUME ["/data"]

ENTRYPOINT ["meeting-pipeline-2"]
CMD ["--help"]
