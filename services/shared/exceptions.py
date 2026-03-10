from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Unified HTTP exception handler.
    - Auth paths (/api/auth/*) return {"error": "..."} to match Java AuthController shape.
    - All other paths return {"message": "..."} per api-compatibility-rules.md R-ERR-2.
    """
    path = request.url.path
    if path.startswith("/api/auth"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Maps FastAPI 422 Unprocessable Entity → 400 Bad Request.
    Returns {"message": "..."} shape per R-ERR-2.
    Wraps Pydantic validation errors into a readable message string.
    """
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc = " -> ".join(str(l) for l in first.get("loc", []) if l != "body")
        msg = first.get("msg", "Validation error")
        detail = f"{loc}: {msg}" if loc else msg
    else:
        detail = "Invalid request"

    path = request.url.path
    if path.startswith("/api/auth"):
        return JSONResponse(status_code=400, content={"error": detail})
    return JSONResponse(status_code=400, content={"message": detail})
