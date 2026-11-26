from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app import security
from app.books.quotations import service
from app.books.quotations.schemas import (
    BooksQuotationCreate,
    BooksQuotationResponse,
    BooksQuotationUpdate,
)
from app.database import get_db

router = APIRouter(
    prefix="/books/quotations",
    tags=["BOOKS - Quotations"],
)


@router.post(
    "/",
    response_model=BooksQuotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a BOOKS quotation",
)
def create_quotation(
    payload: BooksQuotationCreate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.create_quotation(db=db, company_id=current_user.company_id, payload=payload)


@router.get(
    "/",
    response_model=List[BooksQuotationResponse],
    summary="List BOOKS quotations",
)
def list_quotations(
    status_filter: Annotated[Optional[str], Query(description="Filter by quotation status")] = None,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.list_quotations(
        db=db,
        company_id=current_user.company_id,
        status_filter=status_filter,
    )


@router.get(
    "/{quotation_id}",
    response_model=BooksQuotationResponse,
    summary="Get a BOOKS quotation by ID",
)
def get_quotation(
    quotation_id: Annotated[int, Path(ge=1)],
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_authenticated),
):
    return service.get_quotation(db=db, company_id=current_user.company_id, quotation_id=quotation_id)


@router.put(
    "/{quotation_id}",
    response_model=BooksQuotationResponse,
    summary="Update a BOOKS quotation",
)
def update_quotation(
    quotation_id: Annotated[int, Path(ge=1)],
    payload: BooksQuotationUpdate,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.update_quotation(
        db=db,
        company_id=current_user.company_id,
        quotation_id=quotation_id,
        payload=payload,
    )


@router.post(
    "/{quotation_id}/status/{target_status}",
    response_model=BooksQuotationResponse,
    summary="Transition BOOKS quotation status",
)
def transition_quotation_status(
    quotation_id: Annotated[int, Path(ge=1)],
    target_status: str,
    db: Session = Depends(get_db),
    current_user: security.User = Depends(security.require_admin),
):
    return service.transition_quotation_status(
        db=db,
        company_id=current_user.company_id,
        quotation_id=quotation_id,
        target_status=target_status,
    )
