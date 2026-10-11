from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from typing import Iterator

from docugit.extractors import SUPPORTED_EXTENSIONS, extract_text


class DocumentRepository:
    """Stores current documents separately from immutable version snapshots."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.documents_dir = self.root / "documents"
        self.metadata_dir = self.root / ".docugit"
        self.objects_dir = self.metadata_dir / "objects"
        self.published_backups_dir = self.metadata_dir / "published-backups"
        self.database_path = self.metadata_dir / "docugit.sqlite3"
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.published_backups_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    extension TEXT NOT NULL,
                    source_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    current_version INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    version_number INTEGER NOT NULL,
                    commit_title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    UNIQUE(document_id, version_number)
                );
                CREATE INDEX IF NOT EXISTS versions_document_idx
                    ON versions(document_id, version_number DESC);
                """
            )
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(documents)")
            }
            if "source_path" not in columns:
                connection.execute("ALTER TABLE documents ADD COLUMN source_path TEXT")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _validate_source(source: str | Path) -> Path:
        source = Path(source).expanduser().resolve()
        if not source.is_file():
            raise ValueError("Choose an existing document file.")
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError("Only .docx and .xlsx files are supported.")
        return source

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _copy_atomic(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            shutil.copy2(source, temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def list_documents(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents ORDER BY file_name COLLATE NOCASE"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, document_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        if row is None:
            raise ValueError("That document is no longer in the repository.")
        return dict(row)

    def current_path(self, document_id: str) -> Path:
        return self.documents_dir / self.get_document(document_id)["file_name"]

    def add_document(self, source: str | Path, title: str, author: str) -> dict:
        source = self._validate_source(source)
        title = title.strip()
        if not title:
            raise ValueError("Enter a commit title.")

        stem, suffix = source.stem, source.suffix.lower()
        with self._connect() as connection:
            candidate = f"{stem}{suffix}"
            copy_number = 2
            while connection.execute(
                "SELECT 1 FROM documents WHERE file_name = ? COLLATE NOCASE", (candidate,)
            ).fetchone():
                candidate = f"{stem} ({copy_number}){suffix}"
                copy_number += 1

            document_id = uuid.uuid4().hex
            timestamp = self._timestamp()
            object_relative = f"{document_id}/v0001{suffix}"
            snapshot = self.objects_dir / object_relative
            current = self.documents_dir / candidate
            try:
                connection.execute(
                    """INSERT INTO documents
                    (id, file_name, extension, source_path, created_at, updated_at, current_version)
                    VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (document_id, candidate, suffix, str(source), timestamp, timestamp),
                )
                self._copy_atomic(source, snapshot)
                self._copy_atomic(source, current)
                connection.execute(
                    """INSERT INTO versions
                    (document_id, version_number, commit_title, author, timestamp,
                     stored_path, sha256, file_size)
                    VALUES (?, 1, ?, ?, ?, ?, ?, ?)""",
                    (
                        document_id,
                        title,
                        author,
                        timestamp,
                        object_relative,
                        self._digest(source),
                        source.stat().st_size,
                    ),
                )
            except Exception:
                snapshot.unlink(missing_ok=True)
                current.unlink(missing_ok=True)
                raise
        return self.get_document(document_id)

    def list_versions(self, document_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM versions WHERE document_id = ?
                ORDER BY version_number DESC""",
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_version(self, document_id: str, version_number: int) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM versions
                WHERE document_id = ? AND version_number = ?""",
                (document_id, version_number),
            ).fetchone()
        if row is None:
            raise ValueError("That version could not be found.")
        return dict(row)

    def version_path(self, version: dict) -> Path:
        return self.objects_dir / version["stored_path"]

    def create_version(
        self, document_id: str, source: str | Path, title: str, author: str
    ) -> dict:
        source = self._validate_source(source)
        document = self.get_document(document_id)
        if source.suffix.lower() != document["extension"]:
            raise ValueError(f"This document requires a {document['extension']} file.")
        title = title.strip()
        if not title:
            raise ValueError("Enter a commit title.")

        with self._connect() as connection:
            current = connection.execute(
                "SELECT current_version FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if current is None:
                raise ValueError("That document is no longer in the repository.")
            version_number = current["current_version"] + 1
            timestamp = self._timestamp()
            object_relative = f"{document_id}/v{version_number:04d}{document['extension']}"
            snapshot = self.objects_dir / object_relative
            working_copy = self.documents_dir / document["file_name"]
            old_working_copy = working_copy.with_name(
                f".{working_copy.name}.{uuid.uuid4().hex}.bak"
            )
            try:
                if working_copy.exists():
                    shutil.copy2(working_copy, old_working_copy)
                self._copy_atomic(source, snapshot)
                self._copy_atomic(source, working_copy)
                connection.execute(
                    """INSERT INTO versions
                    (document_id, version_number, commit_title, author, timestamp,
                     stored_path, sha256, file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        document_id,
                        version_number,
                        title,
                        author,
                        timestamp,
                        object_relative,
                        self._digest(source),
                        source.stat().st_size,
                    ),
                )
                connection.execute(
                    "UPDATE documents SET current_version = ?, updated_at = ? WHERE id = ?",
                    (version_number, timestamp, document_id),
                )
            except Exception:
                snapshot.unlink(missing_ok=True)
                if old_working_copy.exists():
                    os.replace(old_working_copy, working_copy)
                raise
            finally:
                old_working_copy.unlink(missing_ok=True)
        return self.get_version(document_id, version_number)

    def commit_current(self, document_id: str, title: str, author: str) -> dict:
        """Snapshot the selected document's tracked working copy."""
        working_copy = self.current_path(document_id)
        if not working_copy.is_file():
            raise ValueError("The tracked working copy is missing. Open or restore the document first.")
        digest = self._digest(working_copy)
        versions = self.list_versions(document_id)
        if versions and digest == versions[0]["sha256"]:
            raise ValueError("There are no changes to commit.")
        return self.create_version(document_id, working_copy, title, author)

    def set_original_path(self, document_id: str, source: str | Path) -> Path:
        """Associate a legacy tracked document with its untouched original file."""
        source = self._validate_source(source)
        document = self.get_document(document_id)
        if source.suffix.lower() != document["extension"]:
            raise ValueError(f"This document requires a {document['extension']} file.")
        if source == self.current_path(document_id).resolve():
            raise ValueError("Choose the original file, not the tracked working copy.")
        with self._connect() as connection:
            connection.execute(
                "UPDATE documents SET source_path = ? WHERE id = ?",
                (str(source), document_id),
            )
        return source

    def publish_current(self, document_id: str, title: str, author: str) -> dict:
        """Commit pending edits, archive the original, and publish the working copy."""
        document = self.get_document(document_id)
        if not document["source_path"]:
            raise ValueError("Link this document to its original file before publishing.")
        original = Path(document["source_path"])
        if not original.is_file():
            raise ValueError("The original file is missing. Link the document to its current location.")

        working_copy = self.current_path(document_id)
        if original.resolve() == working_copy.resolve():
            versions = self.list_versions(document_id)
            if not versions:
                raise ValueError("This document has no committed version to publish.")
            return {"version": versions[0], "original_path": original, "backup_path": None}

        versions = self.list_versions(document_id)
        if not working_copy.is_file():
            raise ValueError("The tracked working copy is missing. Open or restore the document first.")
        if versions and self._digest(working_copy) == versions[0]["sha256"]:
            version = versions[0]
        else:
            version = self.commit_current(document_id, title, author)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = (
            self.published_backups_dir
            / document_id
            / f"before-v{version['version_number']:04d}-{timestamp}{original.suffix.lower()}"
        )
        self._copy_atomic(original, backup)
        self._copy_atomic(working_copy, original)
        return {"version": version, "original_path": original, "backup_path": backup}

    def restore_version(self, document_id: str, version_number: int, author: str) -> dict:
        version = self.get_version(document_id, version_number)
        return self.create_version(
            document_id,
            self.version_path(version),
            f"Restore v{version_number:04d}: {version['commit_title']}",
            author,
        )

    def document_text(self, document_id: str) -> str:
        return extract_text(self.current_path(document_id))

    def compare_versions(
        self, document_id: str, old_number: int, new_number: int
    ) -> str:
        old_version = self.get_version(document_id, old_number)
        new_version = self.get_version(document_id, new_number)
        old_text = extract_text(self.version_path(old_version)).splitlines()
        new_text = extract_text(self.version_path(new_version)).splitlines()
        diff = unified_diff(
            old_text,
            new_text,
            fromfile=f"v{old_number:04d}",
            tofile=f"v{new_number:04d}",
            lineterm="",
        )
        return "\n".join(diff)