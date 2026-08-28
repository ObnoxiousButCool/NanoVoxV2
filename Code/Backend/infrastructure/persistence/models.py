"""Declarative base for the ORM mapping.

The explicit naming convention matters: without it SQLite leaves indexes and
constraints unnamed, and Alembic then cannot generate a reversible migration for
them. Setting it before the first table is created avoids a painful correction
later.

Table definitions arrive with the phase that introduces them (P1 onward); this
module intentionally defines only the base and its metadata.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for every mapped entity."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
