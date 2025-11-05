import os
from typing import Dict, List, Optional

from fastapi import Security, HTTPException, Depends, status
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

API_KEY_NAME = "X-API-Key"

api_key_header = APIKeyHeader(
    name=API_KEY_NAME, auto_error=False, description="Enter your API key"
)

API_KEY = os.getenv("API_KEY")

API_KEYS: Dict[str, Dict[str, List[str]]] = {
    API_KEY: {"role": "admin", "scopes": ["*"]},
}

EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json"}


async def get_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Validate API key from header and return it if valid.
    Raises 401 if missing, 403 if invalid.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key header is missing",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key.startswith("Bearer "):
        api_key = api_key[7:]

    if api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
    return api_key


def requires_api_key(api_key: str = Depends(get_api_key)) -> str:
    """
    Dependency for routes that require API key authentication.
    Use this in your route definitions:

    @app.get("/protected")
    async def protected_route(api_key: str = Depends(requires_api_key)):
        return {"message": "Access granted"}
    """
    return api_key


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check API key for all requests except excluded paths.
    Returns 403 JSON response on missing or invalid key.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if any(path == p or path.startswith(f"{p}/") for p in EXCLUDED_PATHS):
            return await call_next(request)

        api_key = request.headers.get(API_KEY_NAME)

        if api_key and api_key.startswith("Bearer "):
            api_key = api_key[7:]

        if not api_key or api_key not in API_KEYS:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid or missing API Key"},
            )

        return await call_next(request)
