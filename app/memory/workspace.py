from typing import Any

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger("workspace")


class Workspace:
    def __init__(self, workspace_id: str):
        self.id = workspace_id
        self.projects: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "project_count": len(self.projects)}


class WorkspaceManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._workspaces: dict[str, Workspace] = {}

    def create_workspace(self, workspace_id: str) -> Workspace:
        if workspace_id not in self._workspaces:
            self._workspaces[workspace_id] = Workspace(workspace_id)
            logger.log_action(
                "workspace", "created", "completed", details={"workspace_id": workspace_id}
            )
        return self._workspaces[workspace_id]

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        return self._workspaces.get(workspace_id)

    def delete_workspace(self, workspace_id: str) -> bool:
        if workspace_id in self._workspaces:
            del self._workspaces[workspace_id]
            logger.log_action(
                "workspace", "deleted", "completed", details={"workspace_id": workspace_id}
            )
            return True
        return False

    def list_workspaces(self) -> list[dict[str, Any]]:
        return [w.to_dict() for w in self._workspaces.values()]

    def ensure_default(self) -> None:
        if "default" not in self._workspaces:
            self.create_workspace("default")


_workspace_manager: WorkspaceManager | None = None


def get_workspace_manager() -> WorkspaceManager:
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
        _workspace_manager.ensure_default()
    return _workspace_manager
