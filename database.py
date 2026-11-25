"""SQLAlchemy models and persistence helpers for the local ledger."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, String, Text, URL, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("KAKEIBO_DB_PATH", APP_DIR / "data" / "kakeibo.db")).expanduser().resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    URL.create("sqlite", database=str(DB_PATH)),
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("kind IN ('支出', '収入')", name="ck_transactions_kind"),
        CheckConstraint("amount >= 0", name="ck_transactions_amount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    store: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    memo: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


def initialize_database() -> None:
    """Create missing tables while preserving existing SQLite records."""
    Base.metadata.create_all(engine)


def list_transactions() -> list[dict[str, Any]]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(Transaction).order_by(Transaction.date.desc(), Transaction.id.desc())
        ).all()
        return [
            {
                "id": row.id,
                "date": row.date.isoformat(),
                "kind": row.kind,
                "category": row.category,
                "store": row.store,
                "amount": row.amount,
                "memo": row.memo,
                "created_at": row.created_at.isoformat(sep=" ") if row.created_at else "",
            }
            for row in rows
        ]


def add_transaction(
    transaction_date: date,
    kind: str,
    category: str,
    store: str,
    amount: int,
    memo: str = "",
) -> int:
    with SessionLocal() as session:
        row = Transaction(
            date=transaction_date,
            kind=kind,
            category=category,
            store=store,
            amount=amount,
            memo=memo,
        )
        session.add(row)
        session.commit()
        return row.id


def update_transactions(rows: list[dict[str, Any]]) -> None:
    with SessionLocal() as session:
        for values in rows:
            row = session.get(Transaction, int(values["id"]))
            if row is None:
                continue
            row.date = values["date"] if isinstance(values["date"], date) else date.fromisoformat(str(values["date"]))
            row.kind = str(values["kind"])
            row.category = str(values["category"])
            row.store = str(values["store"])
            row.amount = int(values["amount"])
            row.memo = str(values["memo"])
        session.commit()


def delete_transactions(transaction_ids: list[int]) -> None:
    if not transaction_ids:
        return
    with SessionLocal() as session:
        session.execute(delete(Transaction).where(Transaction.id.in_(transaction_ids)))
        session.commit()
