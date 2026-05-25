from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import MealRating, MenuItem, Order, OrderItem, OrderStatus, User
from app.schemas import MealRatingCreate, MealRatingRead, MealRatingSummaryRead


def _assert_menu_item_exists(session: Session, menu_item_id: int) -> MenuItem:
    item = session.get(MenuItem, menu_item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jelo nije pronađeno",
        )
    return item


def _assert_user_ordered_menu_item(
    session: Session, current_user: User, menu_item_id: int
) -> None:
    ordered_item = session.exec(
        select(OrderItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.user_id == current_user.id,
            OrderItem.menu_item_id == menu_item_id,
            Order.status != OrderStatus.cancelled,
        )
    ).first()
    if ordered_item is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Možete ocijeniti samo jelo koje ste naručili",
        )


def create_meal_rating(
    session: Session, current_user: User, payload: MealRatingCreate
) -> MealRatingRead:
    _assert_menu_item_exists(session, payload.menu_item_id)
    _assert_user_ordered_menu_item(session, current_user, payload.menu_item_id)

    existing = session.exec(
        select(MealRating).where(
            MealRating.user_id == current_user.id,
            MealRating.menu_item_id == payload.menu_item_id,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Jelo ste već ocijenili",
        )

    row = MealRating(
        user_id=current_user.id,
        menu_item_id=payload.menu_item_id,
        rating=payload.rating,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return MealRatingRead.model_validate(row)


def get_my_ratings(session: Session, current_user: User) -> list[MealRatingRead]:
    rows = session.exec(
        select(MealRating)
        .where(MealRating.user_id == current_user.id)
        .order_by(MealRating.created_at.desc())
    ).all()
    return [MealRatingRead.model_validate(row) for row in rows]


def get_rating_summary(
    session: Session, menu_item_ids: list[int] | None = None
) -> list[MealRatingSummaryRead]:
    stmt = (
        select(
            MealRating.menu_item_id,
            func.avg(MealRating.rating),
            func.count(MealRating.id),
        )
        .group_by(MealRating.menu_item_id)
        .order_by(MealRating.menu_item_id.asc())
    )
    if menu_item_ids:
        unique_ids = sorted({int(v) for v in menu_item_ids if int(v) > 0})
        if unique_ids:
            stmt = stmt.where(MealRating.menu_item_id.in_(unique_ids))

    rows = session.exec(stmt).all()
    result: list[MealRatingSummaryRead] = []
    for menu_item_id, avg_rating, count_rating in rows:
        result.append(
            MealRatingSummaryRead(
                menu_item_id=int(menu_item_id),
                average_rating=round(float(avg_rating or 0.0), 2),
                rating_count=int(count_rating or 0),
            )
        )
    return result
