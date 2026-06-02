"""Ephemeral filesystem for workspace-scoped file operations."""

import shutil
import tempfile
from pathlib import Path


class EphemeralFS:
    """Creates temp directories per workspace and auto-cleans them.

    Provides isolated file storage scoped to a workspace lifecycle.
    """

    def __init__(self, base_dir: str | None = None) -> None:
        """Initialize the ephemeral filesystem.

        Args:
            base_dir: Optional root directory. If None, a temp directory
                is created via tempfile.mkdtemp.
        """
        if base_dir is None:
            base_dir = tempfile.mkdtemp(prefix="agentos_sandbox_")
        self.base_dir = Path(base_dir)

    def create_workspace(self, workspace_id: str) -> Path:
        """Create a subdirectory for the given workspace.

        Args:
            workspace_id: Unique identifier for the workspace.

        Returns:
            Path to the created workspace directory.
        """
        path = self.base_dir / workspace_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_file(self, workspace_id: str, path: str, content: str) -> Path:
        """Write content to a file within a workspace.

        Ensures all parent directories exist.

        Args:
            workspace_id: Workspace identifier.
            path: Relative file path within the workspace.
            content: String content to write.

        Returns:
            Path to the written file.
        """
        full_path = self.base_dir / workspace_id / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return full_path

    def read_file(self, workspace_id: str, path: str) -> str:
        """Read content from a file within a workspace.

        Args:
            workspace_id: Workspace identifier.
            path: Relative file path within the workspace.

        Returns:
            File contents as a string.
        """
        full_path = self.base_dir / workspace_id / path
        return full_path.read_text(encoding="utf-8")

    def delete_workspace(self, workspace_id: str) -> None:
        """Remove a workspace directory and all its contents.

        Args:
            workspace_id: Workspace identifier to remove.
        """
        path = self.base_dir / workspace_id
        if path.exists():
            shutil.rmtree(path)

    def cleanup(self) -> None:
        """Remove the entire base directory and all workspace data."""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)

    def get_workspace_path(self, workspace_id: str) -> Path:
        """Return the path to a workspace directory.

        Args:
            workspace_id: Workspace identifier.

        Returns:
            Path object for the workspace.
        """
        return self.base_dir / workspace_id
