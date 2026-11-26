from typing import Annotated, List
from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app import security
from app.books.payments_received import service
from app.books.payments_received.schemas import (
    PaymentAllocationResponse,
    PaymentReceivedCreate,
    PaymentReceivedResponse,
    PaymentReceivedUpdate,
)
from app.database import get_db

router = APIRouter(
    prefix="/books/payments-received",
    tags=["BOOKS - Payments Received"],
)


@router.post(
    "/",
    response_model=PaymentReceivedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a BOOKS customer payment",
)
def create_payment(
    payload: PaymentReceivedCreate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.create_payment(db=db, company_id=current_user.company_id, payload=payload)


@router.get(
    "/",
    response_model=List[PaymentReceivedResponse],
    summary="List BOOKS payments received",
)
def list_payments(
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.list_payments(db=db, company_id=current_user.company_id)


@router.get(
    "/{payment_id}",
    response_model=PaymentReceivedResponse,
    summary="Get a BOOKS payment received by ID",
)
def get_payment(
    payment_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.get_payment(db=db, company_id=current_user.company_id, payment_id=payment_id)


@router.put(
    "/{payment_id}",
    response_model=PaymentReceivedResponse,
    summary="Update a pending BOOKS payment",
)
def update_pending_payment(
    payment_id: Annotated[int, Path(ge=1)],
    payload: PaymentReceivedUpdate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.update_pending_payment(
        db=db,
        company_id=current_user.company_id,
        payment_id=payment_id,
        payload=payload,
    )


@router.post(
    "/{payment_id}/advance",
    response_model=PaymentReceivedResponse,
    summary="Advance BOOKS payment approval / cheque clearance status",
)
def advance_payment_status(
    payment_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.advance_payment_status(db=db, company_id=current_user.company_id, payment_id=payment_id)


@router.post(
    "/{payment_id}/auto-pay",
    response_model=List[PaymentAllocationResponse],
    summary="Auto-allocate approved BOOKS payment to oldest due open invoices",
)
def auto_pay_invoices(
    payment_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.auto_pay_invoices(db=db, company_id=current_user.company_id, payment_id=payment_id)
