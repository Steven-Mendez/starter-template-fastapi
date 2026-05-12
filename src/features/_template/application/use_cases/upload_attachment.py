"""UploadAttachment use case.

Demonstrates how a feature consumes :class:`FileStoragePort` to persist
opaque blobs. The use case looks up the parent ``thing``, then writes
the payload to the storage port under a deterministic key prefix.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from src.features._template.application.errors import ApplicationError
from src.features._template.application.ports.outbound.thing_repository import (
    ThingRepositoryPort,
)
from src.features.file_storage.application.ports.file_storage_port import (
    FileStoragePort,
)
from src.platform.shared.result import Err, Ok, Result


@dataclass(frozen=True, slots=True)
class UploadAttachmentCommand:
    thing_id: UUID
    content: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class Attachment:
    thing_id: UUID
    key: str
    content_type: str
    size_bytes: int


@dataclass(slots=True)
class UploadAttachmentUseCase:
    repository: ThingRepositoryPort
    file_storage: FileStoragePort

    def execute(
        self, command: UploadAttachmentCommand
    ) -> Result[Attachment, ApplicationError]:
        thing = self.repository.get(command.thing_id)
        if thing is None:
            return Err(ApplicationError.NOT_FOUND)
        key = f"things/{command.thing_id}/{uuid4().hex}"
        result = self.file_storage.put(
            key=key,
            content=command.content,
            content_type=command.content_type,
        )
        if isinstance(result, Err):
            return Err(ApplicationError.STORAGE_FAILED)
        return Ok(
            Attachment(
                thing_id=command.thing_id,
                key=key,
                content_type=command.content_type,
                size_bytes=len(command.content),
            )
        )
