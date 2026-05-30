from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.utils.metrics import get_metrics
from app.utils.rate_limit import limiter

router = APIRouter()
metrics = get_metrics()


class KanbanCardCreate(BaseModel):
    title: str
    description: str = ""
    column: str = "backlog"
    task_id: str = ""
    agent: str = ""


class KanbanCardMove(BaseModel):
    card_id: str
    column: str


@router.post("/api/v1/kanban/{project_id}/cards")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def create_kanban_card(
    project_id: str, card: KanbanCardCreate, request: Request
) -> dict[str, Any]:
    from app.kanban import get_kanban_board

    board = get_kanban_board(project_id)
    created = board.add_card(card.title, card.description, card.column, card.task_id, card.agent)
    metrics.inc("kanban_card_created")
    return {"card": created.to_dict()}


@router.get("/api/v1/kanban/{project_id}")
async def get_kanban_board(project_id: str) -> dict[str, Any]:
    from app.kanban import get_kanban_board

    board = get_kanban_board(project_id)
    return {"columns": board.get_all()}


@router.put("/api/v1/kanban/{project_id}/move")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def move_kanban_card(
    project_id: str, move: KanbanCardMove, request: Request
) -> dict[str, str]:
    from app.kanban import get_kanban_board

    board = get_kanban_board(project_id)
    if not board.move_card(move.card_id, move.column):
        raise HTTPException(status_code=404, detail="Card not found")
    return {"status": "moved"}


@router.delete("/api/v1/kanban/{project_id}/cards/{card_id}")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def delete_kanban_card(project_id: str, card_id: str, request: Request) -> dict[str, str]:
    from app.kanban import get_kanban_board

    board = get_kanban_board(project_id)
    if not board.delete_card(card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    return {"status": "deleted"}
