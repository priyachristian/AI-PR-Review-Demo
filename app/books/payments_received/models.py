from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BooksPaymentReceived(Base):
    """Tenant-scoped BOOKS customer payment received record."""

    __tablename__ = "books_payments_received"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    payment_number = Column(String(50), nullable=False)
    customer_name = Column(String(120), nullable=False)
    payment_mode = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="PENDING")
    amount = Column(Numeric(12, 2, asdecimal=True), nullable=False)
    unused_amount = Column(Numeric(12, 2, asdecimal=True), nullable=False)
    payment_date = Column(Date, nullable=False, default=date.today)
    reference_number = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    allocations = relationship(
        "BooksPaymentAllocation",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "payment_number", name="uq_books_company_payment_number"),
    )


class BooksPaymentAllocation(Base):
    """Allocation of a BOOKS payment received against an issued invoice."""

    __tablename__ = "books_payment_allocations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    payment_id = Column(
        Integer,
        ForeignKey("books_payments_received.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        Integer,
        ForeignKey("books_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_applied = Column(Numeric(12, 2, asdecimal=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)

    payment = relationship("BooksPaymentReceived", back_populates="allocations")
