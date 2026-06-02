"""Tests for the EphemeralFS sandbox filesystem."""

from pathlib import Path

import pytest

from app.sandbox.ephemeral_fs import EphemeralFS


class TestEphemeralFS:
    """Workspace-scoped ephemeral file operations."""

    def test_create_workspace(self, tmp_path: Path) -> None:
        fs = EphemeralFS(base_dir=str(tmp_path / "sandbox"))
        path = fs.create_workspace("ws1")
        assert path.exists()
        assert path.is_dir()
        assert path == tmp_path / "sandbox" / "ws1"

    def test_write_and_read_file(self, tmp_path: Path) -> None:
        fs = EphemeralFS(base_dir=str(tmp_path / "sandbox"))
        fs.create_workspace("ws1")
        written = fs.write_file("ws1", "hello.txt", "Hello, AgentOS!")
        assert written.exists()
        assert written.read_text(encoding="utf-8") == "Hello, AgentOS!"

        content = fs.read_file("ws1", "hello.txt")
        assert content == "Hello, AgentOS!"

    def test_write_file_creates_subdirs(self, tmp_path: Path) -> None:
        fs = EphemeralFS(base_dir=str(tmp_path / "sandbox"))
        fs.create_workspace("ws1")
        written = fs.write_file("ws1", "a/b/c/deep.txt", "nested")
        assert written.exists()
        assert written.parent.name == "c"
        assert fs.read_file("ws1", "a/b/c/deep.txt") == "nested"

    def test_delete_workspace(self, tmp_path: Path) -> None:
        fs = EphemeralFS(base_dir=str(tmp_path / "sandbox"))
        fs.create_workspace("ws1")
        fs.write_file("ws1", "f.txt", "data")
        fs.delete_workspace("ws1")
        assert not (tmp_path / "sandbox" / "ws1").exists()

    def test_cleanup(self, tmp_path: Path) -> None:
        base = tmp_path / "sandbox"
        fs = EphemeralFS(base_dir=str(base))
        fs.create_workspace("ws1")
        fs.create_workspace("ws2")
        fs.cleanup()
        assert not base.exists()

    def test_get_workspace_path(self, tmp_path: Path) -> None:
        fs = EphemeralFS(base_dir=str(tmp_path / "sandbox"))
        fs.create_workspace("ws1")
        path = fs.get_workspace_path("ws1")
        assert path == tmp_path / "sandbox" / "ws1"
        assert path.exists()

    def test_multiple_workspaces(self, tmp_path: Path) -> None:
        fs = EphemeralFS(base_dir=str(tmp_path / "sandbox"))
        fs.create_workspace("alpha")
        fs.create_workspace("beta")
        fs.write_file("alpha", "shared.txt", "alpha data")
        fs.write_file("beta", "shared.txt", "beta data")
        assert fs.read_file("alpha", "shared.txt") == "alpha data"
        assert fs.read_file("beta", "shared.txt") == "beta data"
        # Deleting one does not affect the other
        fs.delete_workspace("alpha")
        with pytest.raises(FileNotFoundError):
            fs.read_file("alpha", "shared.txt")
        assert fs.read_file("beta", "shared.txt") == "beta data"

    def test_write_then_delete_then_read(self, tmp_path: Path) -> None:
        fs = EphemeralFS(base_dir=str(tmp_path / "sandbox"))
        fs.create_workspace("ws1")
        fs.write_file("ws1", "temp.txt", "bye")
        fs.delete_workspace("ws1")
        with pytest.raises(FileNotFoundError):
            fs.read_file("ws1", "temp.txt")
