"""Active connector registry.

The net-worth aggregator iterates whatever this returns, so adding a `BankConnector` in
Phase 1 requires no aggregator change — just register it here.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.connectors.base import AccountConnector
from backend.connectors.manual import ManualConnector


def get_connectors(session: Session, user_id: uuid.UUID) -> list[AccountConnector]:
    return [ManualConnector(session, user_id)]
