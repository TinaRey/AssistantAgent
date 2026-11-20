from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Runtime, get_runtime
from app.integrations.llm import LLMError
from app.schemas.chat import ChatRequest, ChatResponse, PendingAction, ToolTrace

router = APIRouter()

_STATUS = {"rate_limit": 429, "timeout": 504, "auth": 503, "unavailable": 503, "bad_output": 502}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, rt: Runtime = Depends(get_runtime)) -> ChatResponse:
    try:
        return await rt.orchestrator.run(req.messages)
    except LLMError as exc:
        raise HTTPException(_STATUS.get(exc.kind, 502), detail=str(exc)) from exc


@router.get("/traces", response_model=list[ToolTrace])
def traces(rt: Runtime = Depends(get_runtime)) -> list[ToolTrace]:
    return rt.tracer.recent()


@router.get("/actions", response_model=list[PendingAction])
def list_actions(rt: Runtime = Depends(get_runtime)) -> list[PendingAction]:
    return rt.runner.approvals.list()


@router.post("/actions/{action_id}/approve", response_model=PendingAction)
async def approve(action_id: str, rt: Runtime = Depends(get_runtime)) -> PendingAction:
    try:
        return await rt.runner.approve(action_id)
    except KeyError:
        raise HTTPException(404, "Unknown action") from None


@router.post("/actions/{action_id}/reject", response_model=PendingAction)
def reject(action_id: str, rt: Runtime = Depends(get_runtime)) -> PendingAction:
    try:
        return rt.runner.reject(action_id)
    except KeyError:
        raise HTTPException(404, "Unknown action") from None
