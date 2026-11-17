"""API errors (§5): every 4xx/5xx carries {"error": {"code", "message"}}."""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def malformed(message: str = "request body is not valid JSON of the expected shape") -> ApiError:
    return ApiError(400, "malformed_request", message)


def invalid(message: str) -> ApiError:
    return ApiError(422, "validation_failed", message)


def unauthenticated(message: str = "missing or unknown bearer token") -> ApiError:
    return ApiError(401, "unauthenticated", message)


def not_found(message: str = "no such resource") -> ApiError:
    return ApiError(404, "not_found", message)
