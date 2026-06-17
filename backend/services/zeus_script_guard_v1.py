"""Guard para scripts/cron — obliga logging y pasa por services."""

from __future__ import annotations

import functools
import logging
import sys
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def guarded_execution(script_name: str) -> Callable[[F], F]:
    """Decorador para scripts: registra ejecución y advierte mutaciones directas."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from services.zeus_core_guard_v1 import closure_active, validate_critical_action

            logger.info("[SCRIPT_GUARD] start script=%s", script_name)
            if closure_active():
                validate_critical_action(
                    "agents",
                    f"script_{script_name}",
                    layer="script",
                    payload={"script": script_name, "argv": sys.argv[:5]},
                )
            try:
                return fn(*args, **kwargs)
            finally:
                logger.info("[SCRIPT_GUARD] end script=%s", script_name)

        return wrapper  # type: ignore[return-value]

    return decorator
