"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from backend.api import (
    accounts,
    alerts,
    allocations,
    attachments,
    auth,
    banks,
    budgets,
    business_profile,
    cashflow,
    categories,
    clients,
    debts,
    emergency_fund,
    forecast,
    health,
    invoices,
    me,
    networth,
    oneoff_allocations,
    planned_purchases,
    projects,
    recurring,
    recurring_invoices,
    reports,
    rules,
    tax_reserve,
    taxes,
    time_entries,
    transactions,
    trips,
)
from backend.config import get_settings

settings = get_settings()

# Data routers live under /api so nginx can serve the SPA at / on the same origin.
# Docs move under /api too; /health stays at the root for ops/healthchecks.
app = FastAPI(
    title=settings.app_name,
    summary="Self-hosted personal finance tracker",
    version="0.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

API = "/api"
app.include_router(health.router)  # stays at /health, public
app.include_router(auth.router, prefix=API)  # register/login public; /me authed
app.include_router(me.router, prefix=API)
app.include_router(accounts.router, prefix=API)
app.include_router(networth.router, prefix=API)
app.include_router(banks.router, prefix=API)
app.include_router(cashflow.router, prefix=API)
app.include_router(categories.router, prefix=API)
app.include_router(rules.router, prefix=API)
app.include_router(transactions.router, prefix=API)
app.include_router(recurring.router, prefix=API)
app.include_router(reports.router, prefix=API)
app.include_router(budgets.router, prefix=API)
app.include_router(alerts.router, prefix=API)
app.include_router(forecast.router, prefix=API)
app.include_router(debts.router, prefix=API)
app.include_router(allocations.router, prefix=API)
app.include_router(oneoff_allocations.router, prefix=API)
app.include_router(planned_purchases.router, prefix=API)
app.include_router(emergency_fund.router, prefix=API)
app.include_router(tax_reserve.router, prefix=API)
app.include_router(attachments.router, prefix=API)
# Freelance: time tracking + invoicing
app.include_router(business_profile.router, prefix=API)
app.include_router(clients.router, prefix=API)
app.include_router(projects.router, prefix=API)
app.include_router(time_entries.router, prefix=API)
app.include_router(invoices.router, prefix=API)
app.include_router(recurring_invoices.router, prefix=API)
# Taxes: German freelance EÜR + ELSTER helper
app.include_router(taxes.router, prefix=API)
app.include_router(trips.router, prefix=API)


@app.get("/", tags=["root"])
def root() -> dict:
    return {"name": settings.app_name, "docs": "/api/docs"}
