import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

import sentry_sdk
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttachmentDTO:
    """Represents a single attachment file along with its metadata."""

    filename: str
    content: bytes
    mime_type: str


class AttachmentStagingManager:
    """Manages temporary storage and metadata for event attachments."""

    @staticmethod
    def _get_dir_path(event_id: int) -> Path:
        """Returns the specific directory path for a given event."""
        return Path(settings.GENERIC_SUBMISSION_STAGING_ROOT) / str(event_id)

    def stage(self, event_id: int, attachments: List[AttachmentDTO]) -> None:
        """Saves attachments and generates a JSON manifest with exact metadata."""
        dir_path = self._get_dir_path(event_id)
        dir_path.mkdir(parents=True, exist_ok=True)

        manifest_data: List[Dict[str, str]] = []

        for attachment in attachments:
            internal_name = f"{uuid4().hex}_{attachment.filename}"
            file_path = dir_path / internal_name
            file_path.write_bytes(attachment.content)

            manifest_data.append(
                {
                    "original_filename": attachment.filename,
                    "internal_name": internal_name,
                    "mime_type": attachment.mime_type,
                }
            )

        manifest_path = dir_path / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

    def load(self, event_id: int) -> List[AttachmentDTO]:
        """Loads staged attachments and their metadata from the manifest."""
        dir_path = self._get_dir_path(event_id)
        manifest_path = dir_path / "manifest.json"

        if not manifest_path.exists():
            return []

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data: List[Dict[str, str]] = json.load(f)

        result: List[AttachmentDTO] = []
        for item in manifest_data:
            file_path = dir_path / item["internal_name"]
            if file_path.exists():
                result.append(
                    AttachmentDTO(
                        filename=item["original_filename"],
                        content=file_path.read_bytes(),
                        mime_type=item["mime_type"],
                    )
                )

        return result

    def cleanup(self, event_id: int) -> None:
        dir_path: Path = self._get_dir_path(event_id)
        try:
            shutil.rmtree(dir_path)
        except OSError as exc:
            sentry_sdk.api.capture_exception(exc)
            logger.error("Failed to remove staging directory %s for event %s: %s", dir_path, event_id, exc)
