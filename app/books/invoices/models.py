from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BooksInvoice(Base):
    """Tenant-scoped BOOKS Invoice header."""

    __tablename__ = "books_invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    invoice_number = Column(String(50), nullable=False)
    customer_name = Column(String(120), nullable=False)
    issue_date = Column(Date, nullable=False, default=date.today)
    due_date = Column(Date, nullable=False)
    subtotal = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    tax_amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    total_amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    balance_due = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    status = Column(String(30), nullable=False, default="ISSUED")
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    lines = relationship(
        "BooksInvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "invoice_number", name="uq_books_company_invoice_number"),
    )


class BooksInvoiceLine(Base):
    """Line item belonging to a BOOKS Invoice."""

    __tablename__ = "books_invoice_lines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("books_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(200), nullable=False)
    quantity = Column(Numeric(10, 2, asdecimal=True), nullable=False)
    unit_price = Column(Numeric(12, 2, asdecimal=True), nullable=False)
    tax_rate_pct = Column(Numeric(5, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    line_total = Column(Numeric(12, 2, asdecimal=True), nullable=False)

    invoice = relationship("BooksInvoice", back_populates="lines")
