from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.config import settings
from app.models import MenuItem, Order, OrderItem, OrderStatus, User, UserRole
from app.schemas import (
    OrderCreate,
    OrderItemRead,
    OrderRead,
    OrderStatusUpdate,
    OrderUpdate,
    PopularMenuItemStat,
)
from app.services.auth_service import get_user_accessible_org_ids
from app.services.organization_service import assert_organization_orderable_now


def _require_primary_organization_id(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Korisnik nema pridruzenu organizaciju",
        )
    return current_user.organization_id


def normalize_pickup_time(value: datetime) -> datetime:
    pickup_time = value
    if pickup_time.tzinfo is not None:
        pickup_time = pickup_time.astimezone(UTC).replace(tzinfo=None)
    return pickup_time


def validate_pickup_time(value: datetime) -> datetime:
    pickup_time = normalize_pickup_time(value)
    if pickup_time <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vrijeme preuzimanja mora biti u buducnosti",
        )

    if (
        settings.ORDER_WINDOW_START_HOUR is not None
        and settings.ORDER_WINDOW_END_HOUR is not None
    ):
        start = settings.ORDER_WINDOW_START_HOUR
        end = settings.ORDER_WINDOW_END_HOUR
        if start >= end:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Neispravna konfiguracija radnog vremena",
            )
        if pickup_time.hour < start or pickup_time.hour >= end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vrijeme preuzimanja je izvan radnog vremena",
            )

    return pickup_time


def build_order_read(order: Order, session: Session) -> OrderRead:
    items_read: list[OrderItemRead] = []
    total = 0.0
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()
    for oi in order_items:
        menu_item = session.get(MenuItem, oi.menu_item_id)
        items_read.append(
            OrderItemRead(
                id=oi.id,
                menu_item_id=oi.menu_item_id,
                quantity=oi.quantity,
                price_at_order=oi.price_at_order,
                menu_item_name=menu_item.name if menu_item else None,
            )
        )
        total += oi.price_at_order * oi.quantity

    return OrderRead(
        id=order.id,
        user_id=order.user_id,
        organization_id=order.organization_id,
        pickup_time=order.pickup_time,
        status=order.status,
        created_at=order.created_at,
        notes=order.notes,
        items=items_read,
        total_price=round(total, 2),
    )


def _assert_order_access(order: Order, current_user: User, session: Session) -> None:
    if current_user.role in (UserRole.admin, UserRole.owner):
        allowed = set(get_user_accessible_org_ids(session, current_user))
        if order.organization_id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nemate pristup ovoj narudzbi",
            )
        return
    if order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nemate pristup ovoj narudzbi",
        )


def _resolve_order_organization_id(
    session: Session, current_user: User, requested_org_id: int | None
) -> int:
    if requested_org_id is None:
        return _require_primary_organization_id(current_user)

    if current_user.role == UserRole.student:
        return requested_org_id

    allowed = set(get_user_accessible_org_ids(session, current_user))
    if requested_org_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nemate pristup odabranoj organizaciji",
        )
    return requested_org_id


def create_order(
    session: Session,
    current_user: User,
    order_data: OrderCreate,
) -> OrderRead:
    if not order_data.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Narudzba mora sadrzavati barem jedan artikal",
        )

    organization_id = _resolve_order_organization_id(
        session,
        current_user,
        order_data.organization_id,
    )
    assert_organization_orderable_now(session, organization_id)
    pickup_time = validate_pickup_time(order_data.pickup_time)

    order_items: list[OrderItem] = []
    for req in order_data.items:
        menu_item = session.exec(
            select(MenuItem).where(
                MenuItem.id == req.menu_item_id,
                MenuItem.organization_id == organization_id,
            )
        ).first()
        if not menu_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artikal s ID-om {req.menu_item_id} ne postoji",
            )
        if not menu_item.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Artikal '{menu_item.name}' trenutno nije dostupan",
            )
        order_items.append(
            OrderItem(
                menu_item_id=menu_item.id,
                quantity=req.quantity,
                price_at_order=menu_item.price,
            )
        )

    order = Order(
        organization_id=organization_id,
        user_id=current_user.id,
        pickup_time=pickup_time,
        notes=order_data.notes,
    )
    session.add(order)
    session.flush()

    for oi in order_items:
        oi.order_id = order.id
        session.add(oi)

    session.commit()
    session.refresh(order)
    return build_order_read(order, session)


def update_order(
    session: Session,
    current_user: User,
    order_id: int,
    update_data: OrderUpdate,
) -> OrderRead:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Narudzba nije pronadjena",
        )

    _assert_order_access(order, current_user, session)

    if order.status != OrderStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Narudzbu je moguce urediti samo u statusu 'pending'",
        )

    if update_data.pickup_time is not None:
        order.pickup_time = validate_pickup_time(update_data.pickup_time)

    if update_data.notes is not None:
        order.notes = update_data.notes

    if update_data.items is not None:
        assert_organization_orderable_now(session, order.organization_id)
        if len(update_data.items) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Za praznjenje kosarice koristi /orders/{id}/items",
            )

        for existing in list(order.items):
            session.delete(existing)
        session.flush()
        session.expire(order)

        for req in update_data.items:
            menu_item = session.exec(
                select(MenuItem).where(
                    MenuItem.id == req.menu_item_id,
                    MenuItem.organization_id == order.organization_id,
                )
            ).first()
            if not menu_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Artikal s ID-om {req.menu_item_id} ne postoji",
                )
            if not menu_item.is_available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Artikal '{menu_item.name}' trenutno nije dostupan",
                )
            session.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=menu_item.id,
                    quantity=req.quantity,
                    price_at_order=menu_item.price,
                )
            )

    session.add(order)
    session.commit()
    session.refresh(order)
    return build_order_read(order, session)


def clear_order_items(
    session: Session,
    current_user: User,
    order_id: int,
) -> None:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Narudzba nije pronadjena",
        )

    _assert_order_access(order, current_user, session)

    if order.status != OrderStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kosarica se moze prazniti samo u statusu 'pending'",
        )

    for existing in list(order.items):
        session.delete(existing)

    order.status = OrderStatus.cancelled
    session.add(order)
    session.commit()


def get_my_orders(session: Session, current_user: User) -> list[OrderRead]:
    orders = session.exec(
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    ).all()
    return [build_order_read(o, session) for o in orders]


def get_all_orders(session: Session, current_user: User) -> list[OrderRead]:
    allowed = get_user_accessible_org_ids(session, current_user)
    orders = session.exec(
        select(Order)
        .where(Order.organization_id.in_(allowed))
        .order_by(Order.created_at.desc())
    ).all()
    return [build_order_read(o, session) for o in orders]


def get_order_detail(
    session: Session,
    current_user: User,
    order_id: int,
) -> OrderRead:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Narudzba nije pronadjena",
        )

    _assert_order_access(order, current_user, session)
    return build_order_read(order, session)


def update_order_status(
    session: Session,
    current_user: User,
    order_id: int,
    status_update: OrderStatusUpdate,
) -> OrderRead:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Narudzba nije pronadjena",
        )
    _assert_order_access(order, current_user, session)
    order.status = status_update.status
    session.add(order)
    session.commit()
    session.refresh(order)
    return build_order_read(order, session)


def cancel_order(
    session: Session,
    current_user: User,
    order_id: int,
) -> None:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Narudzba nije pronadjena",
        )

    _assert_order_access(order, current_user, session)

    if order.status not in (OrderStatus.pending, OrderStatus.confirmed):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Narudzbu u statusu '{order.status}' nije moguce otkazati",
        )
    order.status = OrderStatus.cancelled
    session.add(order)
    session.commit()


def get_popular_menu_items(
    session: Session,
    current_user: User,
    *,
    limit: int = 8,
    organization_id: int | None = None,
) -> list[PopularMenuItemStat]:
    safe_limit = max(1, min(int(limit or 8), 30))
    allowed_org_ids: list[int] | None = None

    if current_user.role in (UserRole.admin, UserRole.owner):
        accessible = set(get_user_accessible_org_ids(session, current_user))
        if organization_id is not None:
            if organization_id not in accessible:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Nemate pristup odabranoj organizaciji",
                )
            allowed_org_ids = [organization_id]
        else:
            allowed_org_ids = sorted(accessible)
    elif organization_id is not None:
        allowed_org_ids = [organization_id]

    order_count = func.sum(OrderItem.quantity).label("order_count")
    stmt = (
        select(OrderItem.menu_item_id, order_count)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status != OrderStatus.cancelled)
    )
    if allowed_org_ids is not None:
        if not allowed_org_ids:
            return []
        stmt = stmt.where(Order.organization_id.in_(allowed_org_ids))

    rows = session.exec(
        stmt.group_by(OrderItem.menu_item_id)
        .order_by(order_count.desc())
        .limit(safe_limit)
    ).all()

    response: list[PopularMenuItemStat] = []
    for menu_item_id, aggregated_count in rows:
        menu_item = session.get(MenuItem, menu_item_id)
        response.append(
            PopularMenuItemStat(
                menu_item_id=menu_item_id,
                menu_item_name=menu_item.name if menu_item else None,
                order_count=int(aggregated_count or 0),
            )
        )
    return response
