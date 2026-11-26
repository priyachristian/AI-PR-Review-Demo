from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app import security
from app.books.invoices import service
from app.books.invoices.schemas import InvoiceCreate, InvoiceResponse, InvoiceUpdate
from app.database import get_db

router = APIRouter(
    prefix="/books/invoices",
    tags=["BOOKS - Invoices"],
)


@router.post(
    "/",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a BOOKS invoice",
)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.create_invoice(db=db, company_id=current_user.company_id, payload=payload)


@router.get(
    "/",
    response_model=List[InvoiceResponse],
    summary="List BOOKS invoices",
)
def list_invoices(
    status_filter: Annotated[Optional[str], Query(description="Filter by invoice status")] = None,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.list_invoices(
        db=db,
        company_id=current_user.company_id,
        status_filter=status_filter,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get a BOOKS invoice by ID",
)
def get_invoice(
    invoice_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.get_invoice(db=db, company_id=current_user.company_id, invoice_id=invoice_id)


@router.put(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Update a BOOKS invoice",
)
def update_invoice(
    invoice_id: Annotated[int, Path(ge=1)],
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.update_invoice(
        db=db,
        company_id=current_user.company_id,
        invoice_id=invoice_id,
        payload=payload,
    )


@router.post(
    "/{invoice_id}/void",
    response_model=InvoiceResponse,
    summary="Void an unpaid BOOKS invoice",
)
def void_invoice(
    invoice_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.void_invoice(db=db, company_id=current_user.company_id, invoice_id=invoice_id)
