import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from app.utils.logging import get_logger

logger = get_logger("hitl")


class HITLPendingError(Exception):
    def __init__(self, approval_id: str, action: str, message: str = ""):
        self.approval_id = approval_id
        self.action = action
        self.message = (
            message
            or f"HITL required for action: {action}. Use /api/v1/hitl/approve with id={approval_id}"
        )
        super().__init__(self.message)


class HITLRejectedError(Exception):
    pass


class PendingApproval:
    def __init__(self, session_id: str, agent_name: str, action: str, details: dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.session_id = session_id
        self.agent_name = agent_name
        self.action = action
        self.details = details
        self.status = "pending"
        self.created_at = datetime.now(UTC)
        self._event = asyncio.Event()

    def approve(self) -> dict[str, Any]:
        self.status = "approved"
        self._event.set()
        return self.details

    def reject(self, reason: str = "") -> dict[str, Any]:
        self.status = "rejected"
        self._event.set()
        return {"reason": reason, **self.details}

    async def wait(self, timeout: float = 0) -> dict[str, Any]:
        if timeout > 0:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
        else:
            await self._event.wait()
        if self.status == "rejected":
            raise HITLRejectedError(f"Action {self.action} rejected")
        return self.details


class HITLGateway:
    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    async def request_approval(
        self,
        session_id: str,
        agent_name: str,
        action: str,
        details: dict[str, Any],
        timeout: float = 0,
    ) -> dict[str, Any]:
        approval = PendingApproval(session_id, agent_name, action, details)
        self._pending[approval.id] = approval

        logger.log_action(
            agent_id=agent_name,
            action=f"hitl_request:{action}",
            status="pending",
            project_id=session_id,
            details={"approval_id": approval.id, "action": action, **details},
        )

        if timeout > 0:
            asyncio.create_task(self._auto_reject(approval, timeout))

        raise HITLPendingError(
            approval_id=approval.id,
            action=action,
        )

    def approve(self, approval_id: str) -> dict[str, Any]:
        approval = self._pending.get(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        if approval.status != "pending":
            raise ValueError(f"Approval {approval_id} already {approval.status}")
        result = approval.approve()
        logger.log_action(
            agent_id=approval.agent_name,
            action=f"hitl_approved:{approval.action}",
            status="approved",
            project_id=approval.session_id,
            details={"approval_id": approval_id},
        )
        return result

    def reject(self, approval_id: str, reason: str = "") -> dict[str, Any]:
        approval = self._pending.get(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        result = approval.reject(reason)
        logger.log_action(
            agent_id=approval.agent_name,
            action=f"hitl_rejected:{approval.action}",
            status="rejected",
            project_id=approval.session_id,
            details={"approval_id": approval_id, "reason": reason},
        )
        return result

    def get_pending(self) -> list[dict[str, Any]]:
        return [
            {
                "id": a.id,
                "session_id": a.session_id,
                "agent_name": a.agent_name,
                "action": a.action,
                "details": a.details,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in self._pending.values()
            if a.status == "pending"
        ]

    async def cli_confirm(self, action: str, details: dict[str, Any]) -> bool:
        from rich.console import Console
        from rich.prompt import Confirm

        console = Console()
        console.print(f"\n[bold yellow]HITL Required: {action}[/bold yellow]")
        console.print(f"[dim]{details}[/dim]")
        return Confirm.ask("Approve this action?", default=False)

    async def _auto_reject(self, approval: PendingApproval, timeout: float) -> None:
        await asyncio.sleep(timeout)
        if approval.status == "pending":
            approval.reject("auto-rejected: timeout")


_hitl_gateway: HITLGateway | None = None


def get_hitl_gateway() -> HITLGateway:
    global _hitl_gateway
    if _hitl_gateway is None:
        _hitl_gateway = HITLGateway()
    return _hitl_gateway
