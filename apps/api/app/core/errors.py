"""Centralized API error models and exception handlers."""

import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("svario.api")


class ErrorDetail(BaseModel):
    """Standardized error envelope returned by Svario API."""

    error: str
    message: str
    status_code: int
    path: str
    details: Optional[Any] = None


def register_exception_handlers(app: FastAPI) -> None:
    """Attach standardized JSON exception handlers to the FastAPI instance."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        payload = ErrorDetail(
            error="http_error",
            message=str(exc.detail),
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        payload = ErrorDetail(
            error="validation_error",
            message="Request payload or parameters failed validation.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            path=request.url.path,
            details=exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(payload.model_dump()),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s: %s", request.url.path, exc)
        payload: Dict[str, Any] = ErrorDetail(
            error="internal_server_error",
            message="An unexpected error occurred inside Svario API.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            path=request.url.path,
        ).model_dump()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload,
        )
