from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, UniqueConstraint
from app.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(120), index=True, nullable=False)
    department = Column(String(100), nullable=False, default="Engineering")
    role = Column(String(100), nullable=False, default="Software Engineer")
    salary = Column(Numeric(12, 2, asdecimal=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_company_employee_email"),
    )
