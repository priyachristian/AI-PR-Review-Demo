import pytest
from fastapi import HTTPException

from app.crm.contacts import router as contacts_router
from app.crm.contacts.schemas import ContactCreate, ContactUpdate


def test_create_contact_primary_demotion_and_unique_email(db_session, admin_user, other_tenant_admin):
    first = contacts_router.create_contact(
        payload=ContactCreate(
            account_name="Nova Industries",
            full_name="Priya Nair",
            email="priya@example.com",
            job_title="VP Finance",
            is_primary=True,
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert first.is_primary is True

    # Creating a second primary contact on the same account demotes the first
    second = contacts_router.create_contact(
        payload=ContactCreate(
            account_name="nova industries",
            full_name="Karan Mehta",
            email="karan@example.com",
            job_title="Procurement Head",
            is_primary=True,
        ),
        db=db_session,
        current_user=admin_user,
    )
    assert second.is_primary is True

    refreshed_first = contacts_router.get_contact(
        contact_id=first.id,
        db=db_session,
        current_user=admin_user,
    )
    assert refreshed_first.is_primary is False

    # Duplicate email within same tenant -> 409
    with pytest.raises(HTTPException) as dup_exc:
        contacts_router.create_contact(
            payload=ContactCreate(
                account_name="Other Account",
                full_name="Duplicate",
                email="PRIYA@example.com",
            ),
            db=db_session,
            current_user=admin_user,
        )
    assert dup_exc.value.status_code == 409

    # Cross-tenant isolation
    with pytest.raises(HTTPException) as tenant_exc:
        contacts_router.get_contact(
            contact_id=second.id,
            db=db_session,
            current_user=other_tenant_admin,
        )
    assert tenant_exc.value.status_code == 404


def test_delete_primary_contact_blocked_until_demoted(db_session, admin_user):
    contact = contacts_router.create_contact(
        payload=ContactCreate(
            account_name="Vertex Corp",
            full_name="Neha Joshi",
            email="neha@example.com",
            is_primary=True,
        ),
        db=db_session,
        current_user=admin_user,
    )

    with pytest.raises(HTTPException) as exc_info:
        contacts_router.delete_contact(contact_id=contact.id, db=db_session, current_user=admin_user)
    assert exc_info.value.status_code == 409

    contacts_router.update_contact(
        contact_id=contact.id,
        payload=ContactUpdate(is_primary=False),
        db=db_session,
        current_user=admin_user,
    )
    contacts_router.delete_contact(contact_id=contact.id, db=db_session, current_user=admin_user)

    with pytest.raises(HTTPException) as not_found:
        contacts_router.get_contact(contact_id=contact.id, db=db_session, current_user=admin_user)
    assert not_found.value.status_code == 404
