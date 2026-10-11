# -*- coding: utf-8 -*-
"""Byte-exact content snapshots for transfers and recovery.

Small UTF-8 files remain inline for readable diffs. Binary and large files
use immutable temporary snapshots owned by ContentStore. Callers must keep
the store alive until records have been persisted, then close it.

Content descriptions are JSON-compatible metadata. A file-backed ``path``
is an internal temporary reference, never a portable manifest reference.
Persistent storage must copy the snapshot into its own run directory.
"""

import hashlib
import os
import stat
import tempfile


# Bound both streaming memory and the amount of text embedded in records.
CHUNK_BYTES = 256 * 1024
INLINE_TEXT_BYTES = 256 * 1024


def text_content(text):
    """Describe exact UTF-8 text without translating newlines."""
    if not isinstance(text, str):
        raise TypeError('Expected text')
    data = text.encode('utf-8')
    return {
        'encoding': 'utf-8',
        'text': text,
        'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
    }


def _identity(information):
    return (
        information.st_dev,
        information.st_ino,
        information.st_mode,
        information.st_size,
        getattr(information, 'st_mtime_ns', information.st_mtime),
    )


def file_signature(path):
    """Hash an ordinary file in chunks; refuse changes observed while reading."""
    initial = os.lstat(path)
    if not stat.S_ISREG(initial.st_mode):
        raise OSError('Expected an ordinary file: ' + path)
    digest = hashlib.sha256()
    size = 0
    with open(path, 'rb') as handle:
        if _identity(os.fstat(handle.fileno())) != _identity(initial):
            raise OSError('File changed before reading: ' + path)
        while True:
            block = handle.read(CHUNK_BYTES)
            if not block:
                break
            digest.update(block)
            size += len(block)
        final_handle = os.fstat(handle.fileno())
    final_path = os.lstat(path)
    if (
        _identity(initial) != _identity(final_handle)
        or _identity(initial) != _identity(final_path)
        or size != initial.st_size
    ):
        raise OSError('File changed while reading: ' + path)
    return size, digest.hexdigest()


def content_chunks(content):
    """Yield exact bytes from a validated description, with bounded reads."""
    encoding = content.get('encoding')
    if encoding == 'utf-8':
        text = content.get('text')
        if not isinstance(text, str):
            raise ValueError('Missing inline text')
        data = text.encode('utf-8')
        for start in range(0, len(data), CHUNK_BYTES):
            yield data[start:start + CHUNK_BYTES]
    elif encoding == 'blob':
        path = content.get('path')
        if not isinstance(path, str) or not path:
            raise ValueError('Missing snapshot path')
        if not stat.S_ISREG(os.lstat(path).st_mode):
            raise OSError('Snapshot is not an ordinary file: ' + path)
        with open(path, 'rb') as handle:
            while True:
                block = handle.read(CHUNK_BYTES)
                if not block:
                    break
                yield block
    else:
        raise ValueError('Unknown content encoding: %r' % encoding)


def write_verified(handle, content):
    """Stream to an open binary handle and verify the complete payload."""
    size = content.get('size')
    checksum = content.get('sha256')
    if type(size) is not int or size < 0 or not isinstance(checksum, str):
        raise ValueError('Missing content size or checksum')
    digest = hashlib.sha256()
    written = 0
    for block in content_chunks(content):
        count = handle.write(block)
        if count != len(block):
            raise OSError('Incomplete snapshot write')
        written += count
        digest.update(block)
    if written != size or digest.hexdigest() != checksum:
        raise ValueError('Content snapshot checksum mismatch')


def verify_content(content):
    """Verify a description without loading a binary payload into memory."""
    class Sink:
        def write(self, block):
            return len(block)

    write_verified(Sink(), content)


def same_content(first, second):
    """Compare byte identity independently of inline/file-backed storage."""
    return (
        first['size'] == second['size']
        and first['sha256'] == second['sha256']
    )


def matches_file(path, content):
    """Compare an ordinary file with a snapshot; I/O errors remain errors."""
    return file_signature(path) == (content['size'], content['sha256'])


def atomic_install(path, content, before_replace=None):
    """Stage verified bytes beside the target, then atomically replace it.

    ``before_replace`` may recheck the destination immediately before commit.
    A staging, verification or callback failure leaves the destination intact.
    This protects individual writes, not an entire multi-file transaction.
    """
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    descriptor, staged = tempfile.mkstemp(prefix='.forge-content-', dir=parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            write_verified(handle, content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.path.lexists(path):
            information = os.lstat(path)
            if not stat.S_ISREG(information.st_mode):
                raise OSError('Destination is not an ordinary file: ' + path)
            os.chmod(staged, stat.S_IMODE(information.st_mode))
        if before_replace is not None:
            before_replace()
        os.replace(staged, path)
    finally:
        if os.path.exists(staged):
            os.remove(staged)


class ContentStore:
    """Own temporary immutable snapshots until their run has been persisted."""

    def __init__(self):
        self._temporary = None

    def _directory(self):
        if self._temporary is None:
            self._temporary = tempfile.TemporaryDirectory(
                prefix='forge-content-',
            )
        return self._temporary.name

    def close(self):
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def capture(self, path):
        """Snapshot a regular file, refusing observable changes during capture.

        The returned content remains stable if the original is later edited.
        Every successful capture has been flushed before it is returned.
        """
        initial = os.lstat(path)
        if not stat.S_ISREG(initial.st_mode):
            raise OSError('Expected an ordinary file: ' + path)

        descriptor, snapshot = tempfile.mkstemp(dir=self._directory())
        digest = hashlib.sha256()
        size = 0
        preview = bytearray()
        try:
            with os.fdopen(descriptor, 'wb') as destination:
                with open(path, 'rb') as source:
                    if _identity(os.fstat(source.fileno())) != _identity(initial):
                        raise OSError('File changed before capture: ' + path)
                    while True:
                        block = source.read(CHUNK_BYTES)
                        if not block:
                            break
                        if destination.write(block) != len(block):
                            raise OSError('Incomplete snapshot write')
                        digest.update(block)
                        size += len(block)
                        if size <= INLINE_TEXT_BYTES:
                            preview.extend(block)
                        else:
                            preview.clear()
                    final_handle = os.fstat(source.fileno())
                destination.flush()
                os.fsync(destination.fileno())

            if (
                _identity(initial) != _identity(final_handle)
                or _identity(initial) != _identity(os.lstat(path))
                or size != initial.st_size
            ):
                raise OSError('File changed during capture: ' + path)

            if size <= INLINE_TEXT_BYTES:
                try:
                    text = preview.decode('utf-8')
                except UnicodeDecodeError:
                    text = None
                # NUL-containing UTF-8 is treated as binary for presentation.
                if text is not None and '\x00' not in text:
                    os.remove(snapshot)
                    return text_content(text)

            return {
                'encoding': 'blob',
                'path': snapshot,
                'size': size,
                'sha256': digest.hexdigest(),
            }
        except BaseException:
            if os.path.exists(snapshot):
                os.remove(snapshot)
            raise