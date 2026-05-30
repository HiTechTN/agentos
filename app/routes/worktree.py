from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.utils.rate_limit import limiter

router = APIRouter()


class WorktreeCreate(BaseModel):
    branch_name: str
    base_branch: str = "main"


@router.post("/api/v1/rules/init")
@limiter.limit("10/minute")  # type: ignore[untyped-decorator]
async def init_rules(request: Request) -> dict[str, Any]:
    from app.agents.rules import get_rules

    rules = get_rules()
    rules.create_default_agents_md()
    return {"status": "created", "path": "AGENTS.md"}


@router.post("/api/v1/worktree")
@limiter.limit("10/minute")  # type: ignore[untyped-decorator]
async def create_worktree(req: WorktreeCreate, request: Request) -> dict[str, Any]:
    from app.git_worktree import get_worktree_manager

    wm = get_worktree_manager()
    try:
        path = await wm.create_worktree(req.branch_name, req.base_branch)
        return {"status": "created", "branch": req.branch_name, "path": str(path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/v1/worktree")
async def list_worktrees() -> dict[str, Any]:
    from app.git_worktree import get_worktree_manager

    wm = get_worktree_manager()
    try:
        trees = await wm.list_worktrees()
        return {"worktrees": trees}
    except Exception as e:
        return {"worktrees": [], "error": str(e)}


@router.post("/api/v1/worktree/rebase")
@limiter.limit("10/minute")  # type: ignore[untyped-decorator]
async def rebase_worktree(branch_name: str, request: Request) -> dict[str, Any]:
    from app.git_worktree import get_worktree_manager

    wm = get_worktree_manager()
    try:
        await wm.rebase_to_main(branch_name)
        return {"status": "rebased", "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/v1/worktree/{branch_name}")
@limiter.limit("10/minute")  # type: ignore[untyped-decorator]
async def remove_worktree(branch_name: str, request: Request) -> dict[str, Any]:
    from app.git_worktree import get_worktree_manager

    wm = get_worktree_manager()
    try:
        await wm.remove_worktree(branch_name)
        return {"status": "removed", "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
