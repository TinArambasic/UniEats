import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import MenuItem, Organization, User, UserRole
from app.schemas import MenuItemCreate, MenuItemRead, MenuItemUpdate
from app.services.auth_service import get_user_accessible_org_ids
from app.services.image_service import delete_menu_image_file
from app.services.organization_service import is_item_orderable_for_org_now


def _menu_conflict_detail_from_integrity_error(exc: IntegrityError) -> str:
    raw = str(exc.orig).lower() if exc.orig else str(exc).lower()
    if (
        "uq_menu_items_org_code" in raw
        or "menu_items.organization_id, menu_items.code" in raw
    ):
        return "Artikal s tom sifrom vec postoji u odabranoj organizaciji"
    if "unique constraint failed: menu_items.code" in raw:
        return (
            "Artikal s tom sifrom vec postoji. "
            "Baza trenutno ima globalni UNIQUE(code) constraint."
        )
    if (
        "uq_menu_items_org_name" in raw
        or "menu_items.organization_id, menu_items.name" in raw
    ):
        return "Artikal s tim nazivom vec postoji u odabranoj organizaciji"
    return (
        "Konflikt pri spremanju artikla. "
        "Provjerite sifru i naziv unutar odabrane organizacije."
    )


def _resolve_staff_default_organization_id(session: Session, current_user: User) -> int:
    if current_user.organization_id is not None:
        return current_user.organization_id
    accessible = get_user_accessible_org_ids(session, current_user)
    if not accessible:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Korisnik nema pridruzene organizacije",
        )
    return accessible[0]


def _assert_staff_org_access(
    session: Session, current_user: User, organization_id: int
) -> None:
    if current_user.role not in (UserRole.admin, UserRole.owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Potrebne su staff ovlasti",
        )
    allowed = set(get_user_accessible_org_ids(session, current_user))
    if organization_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nemate pristup trazenoj organizaciji",
        )


def _assert_student_org_exists(session: Session, organization_id: int) -> None:
    org = session.exec(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.is_active == True,  # noqa: E712
        )
    ).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacija nije pronadjena",
        )


def _normalize_required_item_name(name: str | None) -> str:
    if name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Naziv artikla je obavezan",
        )
    normalized = name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Naziv artikla je obavezan",
        )
    return normalized


def _normalize_category_name(value: str | None) -> str:
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kategorija je obavezna",
        )
    normalized = " ".join(value.split())
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kategorija je obavezna",
        )
    return normalized


def _normalize_category_token(value: str | None) -> str:
    normalized = " ".join(str(value or "").split()).lower()
    if not normalized:
        return ""
    decomposed = unicodedata.normalize("NFD", normalized)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _assert_non_nullable_update_fields(updates: dict) -> None:
    required_fields = {
        "code": "Sifra artikla je obavezna",
        "group_code": "Kod grupe je obavezan",
        "price": "Cijena je obavezna",
        "category": "Kategorija je obavezna",
        "unit": "Jedinica mjere je obavezna",
        "is_available": "Status dostupnosti je obavezan",
    }
    for field, message in required_fields.items():
        if field in updates and updates[field] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            )


def _ensure_menu_item_conflicts(
    session: Session,
    *,
    organization_id: int,
    code: int,
    name: str,
    exclude_item_id: int | None = None,
) -> None:
    code_stmt = select(MenuItem).where(
        MenuItem.code == code,
        MenuItem.organization_id == organization_id,
    )
    name_stmt = select(MenuItem).where(
        func.lower(MenuItem.name) == name.lower(),
        MenuItem.organization_id == organization_id,
    )
    if exclude_item_id is not None:
        code_stmt = code_stmt.where(MenuItem.id != exclude_item_id)
        name_stmt = name_stmt.where(MenuItem.id != exclude_item_id)

    existing_code = session.exec(code_stmt).first()
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Artikal sa sifrom {code} vec postoji " "u odabranoj organizaciji"
            ),
        )

    existing_name = session.exec(name_stmt).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Artikal s nazivom '{name}' vec postoji " "u odabranoj organizaciji"
            ),
        )


def _build_org_name_map(session: Session, items: list[MenuItem]) -> dict[int, str]:
    organization_ids = {
        int(item.organization_id) for item in items if item.organization_id is not None
    }
    if not organization_ids:
        return {}
    organizations = session.exec(
        select(Organization).where(Organization.id.in_(organization_ids))
    ).all()
    return {int(org.id): org.name for org in organizations if org.id is not None}


def _to_menu_item_read(
    item: MenuItem,
    *,
    organization_name: str | None,
    is_orderable: bool,
) -> MenuItemRead:
    if item.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Neispravan zapis artikla (nedostaje ID)",
        )
    return MenuItemRead(
        id=item.id,
        organization_id=item.organization_id,
        organization_name=organization_name,
        code=item.code,
        name=item.name,
        description=item.description,
        image_url=item.image_url,
        price=item.price,
        category=item.category,
        group_code=item.group_code,
        unit=item.unit,
        is_available=item.is_available,
        is_orderable=is_orderable,
        calories_kcal=item.calories_kcal,
        protein_g=item.protein_g,
        carbs_g=item.carbs_g,
        fat_g=item.fat_g,
    )


def _compute_orderable_value(session: Session, item: MenuItem) -> bool:
    if item.organization_id is None:
        return bool(item.is_available)
    return is_item_orderable_for_org_now(
        session,
        item.organization_id,
        item.is_available,
    )


def _resolve_list_scope(
    session: Session,
    current_user: User,
    organization_id: int | None,
) -> tuple[list[int] | None, bool]:
    """
    Returns:
    - list of organization ids (None means all active organizations for student)
    - whether student has explicit organization selection
    """
    if current_user.role in (UserRole.admin, UserRole.owner):
        if organization_id is None:
            return [_resolve_staff_default_organization_id(session, current_user)], True
        _assert_staff_org_access(session, current_user, organization_id)
        return [organization_id], True

    if organization_id is None:
        return None, False
    _assert_student_org_exists(session, organization_id)
    return [organization_id], True


def get_menu_items(
    session: Session,
    current_user: User,
    available_only: bool,
    category: str | None,
    organization_id: int | None = None,
) -> list[MenuItemRead]:
    org_scope, has_selected_org = _resolve_list_scope(
        session, current_user, organization_id
    )
    stmt = select(MenuItem)
    if org_scope is None:
        stmt = stmt.join(
            Organization, Organization.id == MenuItem.organization_id
        ).where(
            Organization.is_active == True  # noqa: E712
        )
    else:
        stmt = stmt.where(MenuItem.organization_id.in_(org_scope))
    if available_only:
        stmt = stmt.where(MenuItem.is_available == True)  # noqa: E712
    items = session.exec(stmt).all()
    if category:
        selected_token = _normalize_category_token(category)
        items = [
            item
            for item in items
            if _normalize_category_token(item.category) == selected_token
        ]
    org_name_map = _build_org_name_map(session, items)
    responses: list[MenuItemRead] = []
    for item in items:
        if current_user.role == UserRole.student and not has_selected_org:
            is_orderable = False
        else:
            is_orderable = _compute_orderable_value(session, item)
        responses.append(
            _to_menu_item_read(
                item,
                organization_name=(
                    org_name_map.get(int(item.organization_id))
                    if item.organization_id is not None
                    else None
                ),
                is_orderable=is_orderable,
            )
        )
    return responses


def get_menu_item(
    session: Session,
    current_user: User,
    item_id: int,
    organization_id: int | None = None,
) -> MenuItemRead:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artikal nije pronadjen",
        )

    if current_user.role in (UserRole.admin, UserRole.owner):
        _assert_staff_org_access(session, current_user, item.organization_id)
    else:
        allowed_org_ids = set(get_user_accessible_org_ids(session, current_user))
        if organization_id is not None:
            if (
                organization_id not in allowed_org_ids
                or item.organization_id != organization_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Artikal nije pronadjen",
                )
        elif item.organization_id not in allowed_org_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artikal nije pronadjen",
            )
        _assert_student_org_exists(session, item.organization_id)

    org_name_map = _build_org_name_map(session, [item])
    return _to_menu_item_read(
        item,
        organization_name=(
            org_name_map.get(int(item.organization_id))
            if item.organization_id is not None
            else None
        ),
        is_orderable=_compute_orderable_value(session, item),
    )


def create_menu_item(
    session: Session,
    current_user: User,
    item_data: MenuItemCreate,
) -> MenuItemRead:
    organization_id = (
        item_data.organization_id
        if item_data.organization_id is not None
        else _resolve_staff_default_organization_id(session, current_user)
    )
    _assert_staff_org_access(session, current_user, organization_id)
    normalized_name = _normalize_required_item_name(item_data.name)
    _ensure_menu_item_conflicts(
        session,
        organization_id=organization_id,
        code=item_data.code,
        name=normalized_name,
    )
    payload = item_data.model_dump(exclude={"organization_id"})
    payload["name"] = normalized_name
    payload["category"] = _normalize_category_name(payload.get("category"))
    payload["unit"] = str(payload.get("unit", "")).strip() or "KOM"
    item = MenuItem(**payload, organization_id=organization_id)
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_menu_conflict_detail_from_integrity_error(exc),
        ) from exc
    session.refresh(item)
    return _to_menu_item_read(
        item,
        organization_name=(
            _build_org_name_map(session, [item]).get(int(item.organization_id))
            if item.organization_id is not None
            else None
        ),
        is_orderable=_compute_orderable_value(session, item),
    )


def update_menu_item(
    session: Session,
    current_user: User,
    item_id: int,
    item_data: MenuItemUpdate,
) -> MenuItemRead:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artikal nije pronadjen",
        )
    _assert_staff_org_access(session, current_user, item.organization_id)

    updates = item_data.model_dump(exclude_unset=True)
    _assert_non_nullable_update_fields(updates)
    if "name" in updates:
        updates["name"] = _normalize_required_item_name(updates["name"])
    if "unit" in updates and isinstance(updates["unit"], str):
        updates["unit"] = updates["unit"].strip()
        if not updates["unit"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Jedinica mjere je obavezna",
            )
    if "category" in updates and isinstance(updates["category"], str):
        updates["category"] = _normalize_category_name(updates["category"])
    target_org_id = updates.get("organization_id", item.organization_id)
    if target_org_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Artikal nema pridruzenu organizaciju",
        )
    _assert_staff_org_access(session, current_user, target_org_id)

    target_code = updates.get("code", item.code)
    target_name = updates.get("name", item.name)
    _ensure_menu_item_conflicts(
        session,
        organization_id=target_org_id,
        code=target_code,
        name=_normalize_required_item_name(target_name),
        exclude_item_id=item_id,
    )

    old_image_url = item.image_url
    for key, value in updates.items():
        setattr(item, key, value)
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_menu_conflict_detail_from_integrity_error(exc),
        ) from exc
    session.refresh(item)

    if "image_url" in updates and old_image_url != item.image_url:
        delete_menu_image_file(old_image_url)
    return _to_menu_item_read(
        item,
        organization_name=(
            _build_org_name_map(session, [item]).get(int(item.organization_id))
            if item.organization_id is not None
            else None
        ),
        is_orderable=_compute_orderable_value(session, item),
    )


def delete_menu_item(session: Session, current_user: User, item_id: int) -> None:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artikal nije pronadjen",
        )
    _assert_staff_org_access(session, current_user, item.organization_id)
    image_url = item.image_url
    session.delete(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Artikal se ne moze obrisati jer je povezan s postojecim narudzbama",
        ) from exc
    delete_menu_image_file(image_url)


def set_menu_item_image(
    session: Session, current_user: User, item_id: int, image_url: str
) -> MenuItemRead:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artikal nije pronadjen",
        )
    _assert_staff_org_access(session, current_user, item.organization_id)
    old_image_url = item.image_url
    item.image_url = image_url
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Neuspjelo spremanje slike artikla",
        ) from exc
    session.refresh(item)
    if old_image_url != image_url:
        delete_menu_image_file(old_image_url)
    return _to_menu_item_read(
        item,
        organization_name=(
            _build_org_name_map(session, [item]).get(int(item.organization_id))
            if item.organization_id is not None
            else None
        ),
        is_orderable=_compute_orderable_value(session, item),
    )


def clear_menu_item_image(
    session: Session,
    current_user: User,
    item_id: int,
) -> MenuItemRead:
    item = session.get(MenuItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artikal nije pronadjen",
        )
    _assert_staff_org_access(session, current_user, item.organization_id)
    old_image_url = item.image_url
    item.image_url = None
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Neuspjelo uklanjanje slike artikla",
        ) from exc
    session.refresh(item)
    delete_menu_image_file(old_image_url)
    return _to_menu_item_read(
        item,
        organization_name=(
            _build_org_name_map(session, [item]).get(int(item.organization_id))
            if item.organization_id is not None
            else None
        ),
        is_orderable=_compute_orderable_value(session, item),
    )
