import io

import pytest

from app.services.storage import LocalFilesystemStorage


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(root=tmp_path)


def test_saves_and_reads_back(storage):
    ref = storage.save(io.BytesIO(b"video-bytes"), key="abc.mp4")

    with storage.open(ref) as handle:
        assert handle.read() == b"video-bytes"


def test_two_saves_with_the_same_key_do_not_collide(storage):
    first = storage.save(io.BytesIO(b"one"), key="same.mp4")
    second = storage.save(io.BytesIO(b"two"), key="same.mp4")

    assert first != second
    with storage.open(first) as handle:
        assert handle.read() == b"one"
    with storage.open(second) as handle:
        assert handle.read() == b"two"


def test_delete_removes_the_file(storage):
    ref = storage.save(io.BytesIO(b"bye"), key="gone.mp4")

    storage.delete(ref)

    with pytest.raises(FileNotFoundError):
        storage.open(ref)


def test_delete_is_idempotent(storage):
    ref = storage.save(io.BytesIO(b"bye"), key="gone.mp4")
    storage.delete(ref)

    storage.delete(ref)  # must not raise


def test_refs_cannot_escape_the_storage_root(storage):
    with pytest.raises(ValueError):
        storage.open("../../etc/passwd")
