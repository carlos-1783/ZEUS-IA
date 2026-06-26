"""Active ZEUS transaction context (contextvars)."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Optional

_tx_ctx: contextvars.ContextVar[Optional["TransactionContext"]] = contextvars.ContextVar(
    "zeus_tx_ctx", default=None
)


@dataclass
class TransactionContext:
    transaction_id: str
    phase: str = "EXECUTING"  # EXECUTING | COMMITTING


def set_transaction_context(ctx: Optional[TransactionContext]) -> contextvars.Token:
    return _tx_ctx.set(ctx)


def reset_transaction_context(token: contextvars.Token) -> None:
    _tx_ctx.reset(token)


def get_transaction_context() -> Optional[TransactionContext]:
    return _tx_ctx.get()


def get_active_transaction_id() -> Optional[str]:
    ctx = _tx_ctx.get()
    return ctx.transaction_id if ctx else None


def workspace_writes_allowed() -> bool:
    """WORKSPACE writes only during COMMITTING phase when inside a transaction."""
    ctx = _tx_ctx.get()
    if ctx is None:
        return True
    return ctx.phase == "COMMITTING"


def require_transaction_for_module_write(module: str) -> None:
    """Optional strict gate — RRHH/OPS writes must carry transaction_id when enforced."""
    _ = module
