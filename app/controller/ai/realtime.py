from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/realtime", tags=["realtime"])


def runtime(request):
    service = getattr(request.app.state, "realtime_service", None)
    if service is None:
        raise HTTPException(503, "Realtime backend is unavailable")
    return service


@router.get("/events")
def events(request: Request, limit: int = 20):
    runtime(request)
    return request.app.state.backend_tools.q(
        "SELECT event_id,kind,source_id,app_id,occurred_at,status,attempts,error_code,result "
        "FROM ai_events ORDER BY created_at DESC LIMIT ?",
        max(1, min(limit, 100)),
    )


@router.post("/process")
async def process(request: Request):
    return {"processed": await runtime(request).process_one()}


@router.post("/events/{event_id}/retry")
def retry(event_id: str, request: Request):
    runtime(request)
    rows = request.app.state.backend_tools.q(
        "UPDATE ai_events SET status='retry',attempts=0,available_at=now(),error_code=NULL "
        "WHERE event_id=? AND status IN ('failed','waiting_for_model') RETURNING event_id",
        event_id,
    )
    if not rows:
        raise HTTPException(409, "Only failed or waiting events can be retried")
    return {"queued": True}
