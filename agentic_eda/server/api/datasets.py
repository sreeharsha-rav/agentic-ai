"""Dataset upload and inspection.

Upload is deliberately separate from triggering a run: the user uploads, reads
the profile the agents will actually be grounded on, and only then decides to
spend 4-12 minutes and real API credit on an analysis.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from agentic_eda.utils import profile_dataset

from agentic_eda.server.models.schemas import DatasetInfo, DatasetSummary
from agentic_eda.server.services import storage
from agentic_eda.server.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("", response_model=DatasetInfo, status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetInfo:
    """Accept a CSV, stream it to disk, and return its profile.

    Written in chunks rather than `await file.read()` because these datasets run
    to tens of megabytes and buffering one whole in memory per upload is an easy
    way to fall over.
    """
    filename = file.filename or "dataset.csv"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in settings.allowed_upload_suffixes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{suffix or filename}'. "
                f"Expected one of: {', '.join(settings.allowed_upload_suffixes)}"
            ),
        )

    dataset_id, destination = storage.open_upload_target(filename)
    written = 0

    try:
        with destination.open("wb") as sink:
            while True:
                chunk = await file.read(settings.upload_chunk_bytes)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB "
                            "upload limit."
                        ),
                    )
                sink.write(chunk)

        if written == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        try:
            profile = profile_dataset(destination)
        except Exception as exc:
            # A file that pandas cannot parse is useless downstream, so fail here
            # rather than at the first agent several minutes later.
            logger.warning("dataset %s could not be profiled: %s", dataset_id, exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not read this file as CSV: {exc}",
            ) from exc

    except HTTPException:
        storage.discard_upload(dataset_id)
        raise
    except Exception as exc:
        storage.discard_upload(dataset_id)
        logger.exception("upload failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {exc}",
        ) from exc
    finally:
        await file.close()

    rows, columns = storage.parse_shape(profile)
    return DatasetInfo(
        dataset_id=dataset_id,
        filename=destination.name,
        bytes=written,
        uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        profile=profile,
        rows=rows,
        columns=columns,
    )


@router.get("", response_model=list[DatasetSummary])
async def list_datasets() -> list[DatasetSummary]:
    """Previously uploaded datasets, newest first."""
    return [
        DatasetSummary(
            dataset_id=upload.dataset_id,
            filename=upload.filename,
            bytes=upload.bytes,
            uploaded_at=upload.dataset_id[:15],
        )
        for upload in storage.list_uploads()
    ]


@router.get("/{dataset_id}", response_model=DatasetInfo)
async def get_dataset(dataset_id: str) -> DatasetInfo:
    """Re-profile a stored dataset (used when restoring a session)."""
    path = storage.dataset_path(dataset_id)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No dataset with id '{dataset_id}'.",
        )

    try:
        profile = profile_dataset(path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read this file as CSV: {exc}",
        ) from exc

    rows, columns = storage.parse_shape(profile)
    return DatasetInfo(
        dataset_id=dataset_id,
        filename=path.name,
        bytes=path.stat().st_size,
        uploaded_at=dataset_id[:15],
        profile=profile,
        rows=rows,
        columns=columns,
    )
