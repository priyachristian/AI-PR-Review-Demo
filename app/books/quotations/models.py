from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BooksQuotation(Base):
    """Tenant-scoped BOOKS Quotation header."""

    __tablename__ = "books_quotations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    quote_number = Column(String(50), nullable=False)
    customer_name = Column(String(120), nullable=False)
    quote_date = Column(Date, nullable=False, default=date.today)
    expiry_date = Column(Date, nullable=False)
    subtotal = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    discount_amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    tax_amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    total_amount = Column(Numeric(12, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    status = Column(String(30), nullable=False, default="DRAFT")
    created_at = Column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False)

    lines = relationship(
        "BooksQuotationLine",
        back_populates="quotation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "quote_number", name="uq_books_company_quote_number"),
    )


class BooksQuotationLine(Base):
    """Line item belonging to a BOOKS Quotation."""

    __tablename__ = "books_quotation_lines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    quotation_id = Column(
        Integer,
        ForeignKey("books_quotations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description = Column(String(200), nullable=False)
    quantity = Column(Numeric(10, 2, asdecimal=True), nullable=False)
    unit_price = Column(Numeric(12, 2, asdecimal=True), nullable=False)
    tax_rate_pct = Column(Numeric(5, 2, asdecimal=True), nullable=False, default=Decimal("0.00"))
    line_total = Column(Numeric(12, 2, asdecimal=True), nullable=False)

    quotation = relationship("BooksQuotation", back_populates="lines")
