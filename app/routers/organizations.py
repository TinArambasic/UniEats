from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    OrganizationCreate,
    OrganizationListItem,
    OrganizationRead,
    OrganizationUpdate,
)
from app.services import organization_service

router = APIRouter(prefix="/organizations", tags=["Organizacije"])


@router.get(
    "",
    response_model=list[OrganizationListItem],
    summary="Popis organizacija/restorana",
)
def get_organizations(
    q: str | None = Query(None, description="Pretraga po nazivu, gradu ili adresi"),
    city: str | None = Query(None, description="Filtriraj po gradu"),
    favorites_only: bool = Query(False, description="Prikazi samo favorite"),
    sort_by: str | None = Query(
        None,
        description="Sortiranje: name, city, distance",
    ),
    user_latitude: float | None = Query(None, ge=-90, le=90),
    user_longitude: float | None = Query(None, ge=-180, le=180),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return organization_service.list_organizations(
        session=session,
        current_user=current_user,
        q=q,
        city=city,
        favorites_only=favorites_only,
        sort_by=sort_by,
        user_latitude=user_latitude,
        user_longitude=user_longitude,
    )


@router.get(
    "/favorites",
    response_model=list[OrganizationListItem],
    summary="Favoriti restorana",
)
def get_favorite_organizations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return organization_service.list_organizations(
        session=session,
        current_user=current_user,
        favorites_only=True,
    )


@router.post(
    "",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiraj organizaciju (owner)",
)
def create_organization(
    create_data: OrganizationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return organization_service.create_organization(session, current_user, create_data)


@router.post(
    "/{organization_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dodaj restoran u favorite",
)
def add_organization_favorite(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    organization_service.set_favorite(session, current_user, organization_id)


@router.delete(
    "/{organization_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Ukloni restoran iz favorita",
)
def remove_organization_favorite(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    organization_service.remove_favorite(session, current_user, organization_id)


@router.get(
    "/{organization_id}",
    response_model=OrganizationRead,
    summary="Detalji organizacije",
)
def get_organization(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return organization_service.get_organization_detail(
        session, current_user, organization_id
    )


@router.put(
    "/{organization_id}",
    response_model=OrganizationRead,
    summary="Azuriraj organizaciju i radno vrijeme",
)
def put_organization(
    organization_id: int,
    update_data: OrganizationUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return organization_service.update_organization(
        session,
        current_user,
        organization_id,
        update_data,
    )
