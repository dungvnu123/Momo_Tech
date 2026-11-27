from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.services.llm_client import LLMNotConfiguredError


async def run_ai(operation):
    try:
        return await operation
    except LLMNotConfiguredError:
        raise HTTPException(503, "Gemini client is not configured") from None
    except TimeoutError:
        raise HTTPException(504, "AI request timed out") from None
    except Exception:
        raise HTTPException(502, "AI request failed validation or provider execution") from None


async def unhandled_error(request: Request, error: Exception):
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        {"detail": "Internal server error", "request_id": request_id}, status_code=500,
        headers={"X-Request-ID": request_id},
    )
