import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol


class Storage(Protocol):
    """Where original uploaded videos live.

    `save` returns an opaque ref. Callers persist the ref and hand it back to
    `open`, `path_for`, and `delete`; they must never interpret its contents.
    Swapping in S3/MinIO later means writing a second implementation of this
    protocol and changing nothing else.
    """

    def save(self, data: BinaryIO, key: str) -> str: ...

    def open(self, ref: str) -> BinaryIO: ...

    def path_for(self, ref: str) -> Path: ...

    def delete(self, ref: str) -> None: ...


class LocalFilesystemStorage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, ref: str) -> Path:
        candidate = (self.root / ref).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError(f"ref escapes the storage root: {ref!r}")
        return candidate

    def save(self, data: BinaryIO, key: str) -> str:
        ref = f"{uuid.uuid4().hex}-{Path(key).name}"
        destination = self._resolve(ref)
        with destination.open("wb") as out:
            shutil.copyfileobj(data, out)
        return ref

    def open(self, ref: str) -> BinaryIO:
        return self._resolve(ref).open("rb")

    def path_for(self, ref: str) -> Path:
        return self._resolve(ref)

    def delete(self, ref: str) -> None:
        self._resolve(ref).unlink(missing_ok=True)
