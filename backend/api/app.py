"""SmartESS FastAPI application entry point."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.investigations import router as investigations_router
from backend.api.modules import router as m10_router
from backend.api.system import router as system_router

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("smartess")

app = FastAPI(title="SmartESS API", version="0.1.0")

# The Next.js frontend fetches server-side, so CORS is not required for the
# normal path. It is enabled for an explicit allow-list only, so a browser-side
# tool can be pointed at the API during development without opening it to `*`
# (design.md §10.4, §15.2).
_origins = [
    o.strip()
    for o in os.environ.get(
        "SMARTESS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)

app.include_router(investigations_router)
app.include_router(m10_router)
app.include_router(system_router)


@app.get("/health")
def health():
    """Process liveness only. Dependency checks are `GET /readiness`."""
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    logger.info("malformed request %s %s", request.method, request.url.path)
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def main() -> None:
    """Production process. Host defaults to loopback because the API has no auth.

    ``PORT`` is the deployment port. ``SMARTESS_HOST`` overrides the bind address
    when the process is placed behind a private network interface.
    """
    import uvicorn

    host = os.environ.get("SMARTESS_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level=os.environ.get("LOG_LEVEL", "info").lower())


if __name__ == "__main__":
    main()
