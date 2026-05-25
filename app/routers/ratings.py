from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.models import User
from app.schemas import MealRatingCreate, MealRatingRead, MealRatingSummaryRead
from app.services import rating_service

router = APIRouter(prefix="/ratings", tags=["Ocjene"])


@router.get(
    "/my",
    response_model=list[MealRatingRead],
    summary="Moje ocjene jela",
)
def get_my_ratings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return rating_service.get_my_ratings(session, current_user)


@router.get(
    "/summary",
    response_model=list[MealRatingSummaryRead],
    summary="Sažetak ocjena po jelu",
)
def get_ratings_summary(
    menu_item_ids: list[int] | None = Query(
        default=None, description="Opcionalni filter po ID-evima jela"
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    del current_user  # autentifikacija je obavezna
    return rating_service.get_rating_summary(session, menu_item_ids=menu_item_ids)


@router.post(
    "/",
    response_model=MealRatingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ocijeni jelo (jednom po korisniku)",
)
def create_rating(
    payload: MealRatingCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return rating_service.create_meal_rating(session, current_user, payload)
