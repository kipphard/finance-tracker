"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.persistence.database import get_session

SessionDep = Annotated[Session, Depends(get_session)]
