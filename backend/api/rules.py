"""Categorization rule endpoints (§4.3)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import SessionDep
from backend.persistence import repository
from backend.schemas import RuleCreate, RuleOut, RuleUpdate

router = APIRouter(prefix="/rules", tags=["rules"])


def _require_category(session, category_id: uuid.UUID) -> None:
    if repository.get_category(session, category_id) is None:
        raise HTTPException(status_code=400, detail="unknown category")


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(payload: RuleCreate, session: SessionDep) -> RuleOut:
    _require_category(session, payload.category_id)
    rule = repository.create_rule(
        session,
        match_pattern=payload.match_pattern,
        category_id=payload.category_id,
        priority=payload.priority,
    )
    session.commit()
    return RuleOut.model_validate(rule)


@router.get("", response_model=list[RuleOut])
def list_rules(session: SessionDep) -> list[RuleOut]:
    return [RuleOut.model_validate(r) for r in repository.list_rules(session)]


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: uuid.UUID, payload: RuleUpdate, session: SessionDep
) -> RuleOut:
    rule = repository.get_rule(session, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    if payload.category_id is not None:
        _require_category(session, payload.category_id)
    repository.update_rule(session, rule, **payload.model_dump(exclude_unset=True))
    session.commit()
    return RuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: uuid.UUID, session: SessionDep) -> Response:
    if not repository.delete_rule(session, rule_id):
        raise HTTPException(status_code=404, detail="rule not found")
    session.commit()
    return Response(status_code=204)
