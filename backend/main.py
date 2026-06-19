"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from backend.api import (
    accounts,
    banks,
    cashflow,
    categories,
    health,
    networth,
    recurring,
    rules,
    transactions,
)
from backend.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    summary="Self-hosted personal finance tracker — Phase 0 scaffold",
    version="0.0.0",
)

app.include_router(health.router)
app.include_router(accounts.router)
app.include_router(networth.router)
app.include_router(banks.router)
app.include_router(cashflow.router)
app.include_router(categories.router)
app.include_router(rules.router)
app.include_router(transactions.router)
app.include_router(recurring.router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {"name": settings.app_name, "docs": "/docs"}
