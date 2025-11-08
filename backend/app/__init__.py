"""
Application package initialization.
This file makes the app directory a Python package.

To avoid circular-import issues when the model layer imports `app`, we expose
`api_router` lazily via ``__getattr__`` instead of importing it eagerly here.
"""

from importlib import import_module
from typing import Any

__all__ = ["api_router"]


def __getattr__(name: str) -> Any:
    if name == "api_router":
        return import_module("app.api.v1").api_router
    raise AttributeError(f"module 'app' has no attribute {name!r}")
