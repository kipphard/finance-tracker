"""Taxes: German freelance EÜR (Einnahmenüberschussrechnung), §32a estimate, ELSTER prompt."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import (
    ElsterPromptOut,
    EurReportOut,
    ExpenseLineOut,
    TaxLineItemOut,
    TaxProfileOut,
    TaxProfileUpdate,
    TaxYearInputOut,
    TaxYearInputUpdate,
)
from backend.tax.elster import build_elster_prompt
from backend.tax.eur import EurResult, compute_eur

router = APIRouter(prefix="/tax", tags=["taxes"])


def _default_year() -> int:
    return datetime.now(timezone.utc).year


@router.get("/profile", response_model=TaxProfileOut)
def get_profile(session: SessionDep, user: CurrentUser) -> TaxProfileOut:
    profile = repository.get_tax_profile(session, user.id)
    session.commit()  # persist the default row if it was just created
    return TaxProfileOut.model_validate(profile)


@router.patch("/profile", response_model=TaxProfileOut)
def update_profile(
    payload: TaxProfileUpdate, session: SessionDep, user: CurrentUser
) -> TaxProfileOut:
    profile = repository.get_tax_profile(session, user.id)
    fields = payload.model_dump(exclude_unset=True)
    repository.update_tax_profile(session, profile, **fields)
    session.commit()
    return TaxProfileOut.model_validate(profile)


@router.get("/year/{year}", response_model=TaxYearInputOut)
def get_year(year: int, session: SessionDep, user: CurrentUser) -> TaxYearInputOut:
    row = repository.get_tax_year_input(session, user.id, year)
    session.commit()
    return TaxYearInputOut.model_validate(row)


@router.patch("/year/{year}", response_model=TaxYearInputOut)
def update_year(
    year: int, payload: TaxYearInputUpdate, session: SessionDep, user: CurrentUser
) -> TaxYearInputOut:
    row = repository.get_tax_year_input(session, user.id, year)
    repository.update_tax_year_input(session, row, **payload.model_dump(exclude_unset=True))
    session.commit()
    return TaxYearInputOut.model_validate(row)


def _to_out(eur: EurResult) -> EurReportOut:
    return EurReportOut(
        year=eur.year, business_type=eur.business_type,
        is_kleinunternehmer=eur.is_kleinunternehmer,
        income=eur.income, expense_total=eur.expense_total, profit=eur.profit,
        expense_lines=[
            ExpenseLineOut(key=l.key, label=l.label, amount=l.amount,
                           gross=l.gross, percent=l.percent, count=l.count)
            for l in eur.expense_lines
        ],
        line_items=[
            TaxLineItemOut(date=i.date, payee=i.payee, category=i.category, bucket=i.bucket,
                           amount=i.amount, deductible=i.deductible, percent=i.percent, tags=i.tags)
            for i in eur.line_items
        ],
        other_income=eur.other_income, tariff_year=eur.tariff_year,
        tax_with=eur.tax_with, tax_without=eur.tax_without, tax_estimate=eur.tax_estimate,
        home_office_mode=eur.home_office_mode, home_office_days=eur.home_office_days,
        business_km=eur.business_km, km_rate=eur.km_rate,
    )


@router.get("/eur", response_model=EurReportOut)
def eur_report(
    session: SessionDep, user: CurrentUser, year: int = Query(default=None)
) -> EurReportOut:
    eur = compute_eur(session, user.id, year or _default_year())
    session.commit()  # persists any default profile/year rows created during computation
    return _to_out(eur)


@router.get("/elster-prompt", response_model=ElsterPromptOut)
def elster_prompt(
    session: SessionDep, user: CurrentUser, year: int = Query(default=None)
) -> ElsterPromptOut:
    y = year or _default_year()
    business = repository.get_business_profile(session, user.id)
    tax_profile = repository.get_tax_profile(session, user.id)
    year_input = repository.get_tax_year_input(session, user.id, y)
    eur = compute_eur(session, user.id, y)
    session.commit()
    prompt = build_elster_prompt(business, tax_profile, year_input, eur)
    return ElsterPromptOut(year=y, prompt=prompt)


@router.get("/export.csv")
def export_csv(
    session: SessionDep, user: CurrentUser, year: int = Query(default=None)
) -> Response:
    y = year or _default_year()
    eur = compute_eur(session, user.id, y)
    session.commit()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["date", "payee", "category", "bucket", "amount", "deductible", "percent", "tags"])
    for i in eur.line_items:
        writer.writerow([
            i.date, i.payee, i.category or "", i.bucket,
            str(i.amount), str(i.deductible), "" if i.percent is None else str(i.percent),
            ";".join(i.tags),
        ])
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="euer_{y}.csv"'},
    )
