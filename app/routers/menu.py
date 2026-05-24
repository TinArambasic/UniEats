from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlmodel import Session

from app.database import get_session
from app.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas import MenuItemCreate, MenuItemRead, MenuItemUpdate
from app.services import menu_service
from app.services.image_service import delete_menu_image_file, save_menu_item_image

router = APIRouter(prefix="/menu", tags=["Jelovnik"])


@router.get(
    "/items",
    response_model=list[MenuItemRead],
    summary="Jelovnik (autentifikacija obavezna)",
)
def get_menu_items(
    available_only: bool = Query(True, description="Prikazi samo dostupne artikle"),
    category: str | None = Query(None, description="Filtriraj po kategoriji"),
    organization_id: int | None = Query(
        None, description="Ciljana organizacija/restoran"
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return menu_service.get_menu_items(
        session=session,
        current_user=current_user,
        available_only=available_only,
        category=category,
        organization_id=organization_id,
    )


@router.get(
    "/items/{item_id}",
    response_model=MenuItemRead,
    summary="Detalji jednog artikla",
)
def get_menu_item(
    item_id: int,
    organization_id: int | None = Query(
        None, description="Ciljana organizacija/restoran"
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return menu_service.get_menu_item(
        session,
        current_user,
        item_id,
        organization_id=organization_id,
    )


@router.post(
    "/items",
    response_model=MenuItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Dodaj novi artikal (admin/owner)",
)
def create_menu_item(
    item_data: MenuItemCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    return menu_service.create_menu_item(session, current_user, item_data)


@router.put(
    "/items/{item_id}",
    response_model=MenuItemRead,
    summary="Azuriraj artikal (admin/owner)",
)
def update_menu_item(
    item_id: int,
    item_data: MenuItemUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    return menu_service.update_menu_item(session, current_user, item_id, item_data)


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Obrisi artikal (admin/owner)",
)
def delete_menu_item(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    menu_service.delete_menu_item(session, current_user, item_id)


@router.post(
    "/items/{item_id}/image",
    response_model=MenuItemRead,
    summary="Upload slike artikla (admin/owner)",
)
async def upload_menu_item_image(
    item_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    image_url = await save_menu_item_image(file)
    try:
        return menu_service.set_menu_item_image(
            session, current_user, item_id, image_url
        )
    except Exception:
        delete_menu_image_file(image_url)
        raise


@router.delete(
    "/items/{item_id}/image",
    response_model=MenuItemRead,
    summary="Ukloni sliku artikla (admin/owner)",
)
def remove_menu_item_image(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    return menu_service.clear_menu_item_image(session, current_user, item_id)
