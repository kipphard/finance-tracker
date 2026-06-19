"""Portable column types.

These let production run on Postgres-native types (UUID, JSONB) while the test suite
runs on SQLite, without changing the model definitions.
"""
from __future__ import annotations

from sqlalchemy import JSON, Numeric, Uuid
from sqlalchemy.dialects.postgresql import JSONB

# UUID primary keys: native uuid on Postgres, CHAR(32) elsewhere (handled by SQLAlchemy's
# Uuid type, which processes uuid.UUID <-> stored value on both dialects).
GUID = Uuid(as_uuid=True)

# JSON blob: JSONB on Postgres, generic JSON on SQLite.
JSONType = JSONB().with_variant(JSON(), "sqlite")

# Money is always exact Decimal, never float.
Money = Numeric(20, 4)
