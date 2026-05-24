from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas import (
    OrderCreate,
    OrderRead,
    OrderStatusUpdate,
    OrderUpdate,
    PopularMenuItemStat,
)
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Narudzbe"])


@router.post(
    "/",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj novu narudzbu",
)
def create_order(
    order_data: OrderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return order_service.create_order(session, current_user, order_data)


@router.patch(
    "/{order_id}",
    response_model=OrderRead,
    summary="Uredi narudzbu (student ili admin)",
)
def update_order(
    order_id: int,
    update_data: OrderUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return order_service.update_order(session, current_user, order_id, update_data)


@router.delete(
    "/{order_id}/items",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Praznjenje kosarice (brisanje stavki)",
)
def clear_order_items(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    order_service.clear_order_items(session, current_user, order_id)


@router.get(
    "/my",
    response_model=list[OrderRead],
    summary="Sve moje narudzbe",
)
def get_my_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return order_service.get_my_orders(session, current_user)


@router.get(
    "/popular",
    response_model=list[PopularMenuItemStat],
    summary="Najpopularnija jela prema stvarnim narudzbama",
)
def get_popular_menu_items(
    limit: int = Query(8, ge=1, le=30),
    organization_id: int | None = Query(
        None, description="Opcionalni filter po restoranu"
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return order_service.get_popular_menu_items(
        session,
        current_user,
        limit=limit,
        organization_id=organization_id,
    )


@router.get(
    "/all",
    response_model=list[OrderRead],
    summary="Sve narudzbe - admin/owner pregled",
)
def get_all_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    return order_service.get_all_orders(session, current_user)


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    summary="Detalji narudzbe",
)
def get_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return order_service.get_order_detail(session, current_user, order_id)


@router.patch(
    "/{order_id}/status",
    response_model=OrderRead,
    summary="Promijeni status narudzbe (admin/owner)",
)
def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    return order_service.update_order_status(
        session, current_user, order_id, status_update
    )


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Otkazi narudzbu",
)
def cancel_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    order_service.cancel_order(session, current_user, order_id)
