from __future__ import annotations

import math
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import (
    Organization,
    OrganizationWorkingHour,
    User,
    UserFavoriteOrganization,
    UserOrganization,
    UserRole,
)
from app.schemas import (
    OrganizationCreate,
    OrganizationListItem,
    OrganizationUpdate,
)
from app.services.auth_service import get_user_accessible_org_ids

DEFAULT_OPEN_TIME = "08:00"
DEFAULT_CLOSE_TIME = "20:00"
ORDER_CUTOFF_MINUTES = 30


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour = int(value[:2])
    minute = int(value[3:5])
    return hour, minute


def _day_close_datetime(day: datetime, close_time: str) -> datetime:
    h, m = _parse_hhmm(close_time)
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def _day_open_datetime(day: datetime, open_time: str) -> datetime:
    h, m = _parse_hhmm(open_time)
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def _hours_by_day(org: Organization) -> dict[int, OrganizationWorkingHour]:
    return {h.day_of_week: h for h in org.working_hours}


def _is_open_now(org: Organization, now: datetime) -> bool:
    hours_map = _hours_by_day(org)
    today = hours_map.get(now.weekday())
    if not today:
        return False
    if today.is_closed or not today.open_time or not today.close_time:
        return False
    open_dt = _day_open_datetime(now, today.open_time)
    close_dt = _day_close_datetime(now, today.close_time)
    return open_dt <= now < close_dt


def _is_order_allowed_now(org: Organization, now: datetime) -> bool:
    is_allowed, _ = _get_orderability(org, now)
    return is_allowed


def _get_orderability(org: Organization, now: datetime) -> tuple[bool, str | None]:
    if not org.is_active:
        return False, "Restoran trenutno nije aktivan."

    hours_map = _hours_by_day(org)
    today = hours_map.get(now.weekday())
    if not today:
        return False, "Za danas nije definirano radno vrijeme restorana."
    if today.is_closed or not today.open_time or not today.close_time:
        if today.is_closed:
            return False, "Restoran je danas zatvoren."
        return False, "Restoran danas nema kompletno definirano radno vrijeme."
    open_dt = _day_open_datetime(now, today.open_time)
    close_dt = _day_close_datetime(now, today.close_time)
    cutoff = close_dt - timedelta(minutes=ORDER_CUTOFF_MINUTES)
    if now < open_dt:
        return False, f"Restoran se otvara u {today.open_time}."
    if now >= close_dt:
        return False, f"Restoran je zatvoren (radno vrijeme do {today.close_time})."
    if now > cutoff:
        return (
            False,
            "Narudzba je moguca najkasnije "
            f"{ORDER_CUTOFF_MINUTES} minuta prije zatvaranja ({today.close_time}).",
        )
    return True, None


def ensure_organization_default_hours(session: Session, organization_id: int) -> None:
    existing = session.exec(
        select(OrganizationWorkingHour).where(
            OrganizationWorkingHour.organization_id == organization_id
        )
    ).all()
    if len(existing) == 7:
        return
    existing_days = {h.day_of_week for h in existing}
    for day in range(7):
        if day in existing_days:
            continue
        session.add(
            OrganizationWorkingHour(
                organization_id=organization_id,
                day_of_week=day,
                is_closed=False,
                open_time=DEFAULT_OPEN_TIME,
                close_time=DEFAULT_CLOSE_TIME,
            )
        )
    session.commit()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _query_staff_scope_orgs(session: Session, current_user: User) -> list[Organization]:
    ids = get_user_accessible_org_ids(session, current_user)
    return session.exec(select(Organization).where(Organization.id.in_(ids))).all()


def _query_student_scope_orgs(session: Session) -> list[Organization]:
    return session.exec(
        select(Organization).where(Organization.is_active == True)  # noqa: E712
    ).all()


def create_organization(
    session: Session,
    current_user: User,
    create_data: OrganizationCreate,
) -> Organization:
    if current_user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Samo owner moze kreirati organizaciju",
        )
    name = create_data.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Naziv organizacije je obavezan",
        )
    existing = session.exec(
        select(Organization).where(Organization.name == name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organizacija s tim nazivom vec postoji",
        )
    org = Organization(
        name=name,
        address=create_data.address,
        city=create_data.city,
        phone=create_data.phone,
        latitude=create_data.latitude,
        longitude=create_data.longitude,
        is_active=True if create_data.is_active is None else create_data.is_active,
    )
    session.add(org)
    session.commit()
    session.refresh(org)

    existing_link = session.exec(
        select(UserOrganization).where(
            UserOrganization.user_id == current_user.id,
            UserOrganization.organization_id == org.id,
        )
    ).first()
    if not existing_link:
        session.add(UserOrganization(user_id=current_user.id, organization_id=org.id))
        session.commit()

    if create_data.working_hours:
        update_organization(
            session=session,
            current_user=current_user,
            organization_id=org.id,
            update_data=OrganizationUpdate(working_hours=create_data.working_hours),
        )
    else:
        ensure_organization_default_hours(session, org.id)
    session.refresh(org)
    return org


def list_organizations(
    session: Session,
    current_user: User,
    *,
    q: str | None = None,
    city: str | None = None,
    favorites_only: bool = False,
    sort_by: str | None = None,
    user_latitude: float | None = None,
    user_longitude: float | None = None,
) -> list[OrganizationListItem]:
    if current_user.role in (UserRole.admin, UserRole.owner):
        organizations = _query_staff_scope_orgs(session, current_user)
    else:
        organizations = _query_student_scope_orgs(session)

    q_norm = (q or "").strip().lower()
    city_norm = (city or "").strip().lower()

    favorite_ids = set(
        session.exec(
            select(UserFavoriteOrganization.organization_id).where(
                UserFavoriteOrganization.user_id == current_user.id
            )
        ).all()
    )

    now = datetime.now()
    items: list[OrganizationListItem] = []
    for org in organizations:
        ensure_organization_default_hours(session, org.id)
        session.refresh(org)
        text = " ".join(
            [
                org.name or "",
                org.city or "",
                org.address or "",
            ]
        ).lower()
        if q_norm and q_norm not in text:
            continue
        if city_norm and (org.city or "").strip().lower() != city_norm:
            continue
        is_favorite = org.id in favorite_ids
        if favorites_only and not is_favorite:
            continue
        is_open_now = _is_open_now(org, now)
        can_order_now, order_block_reason = _get_orderability(org, now)
        distance_km = None
        if (
            user_latitude is not None
            and user_longitude is not None
            and org.latitude is not None
            and org.longitude is not None
        ):
            distance_km = round(
                _haversine_km(
                    user_latitude, user_longitude, org.latitude, org.longitude
                ),
                2,
            )
        items.append(
            OrganizationListItem(
                id=org.id,
                name=org.name,
                address=org.address,
                city=org.city,
                phone=org.phone,
                latitude=org.latitude,
                longitude=org.longitude,
                is_active=org.is_active,
                is_favorite=is_favorite,
                is_open_now=is_open_now,
                can_order_now=can_order_now,
                order_block_reason=order_block_reason,
                distance_km=distance_km,
            )
        )

    if sort_by == "distance":
        items.sort(
            key=lambda x: (
                x.distance_km is None,
                x.distance_km if x.distance_km is not None else 1e9,
            )
        )
    elif sort_by == "name":
        items.sort(key=lambda x: x.name.lower())
    elif sort_by == "city":
        items.sort(key=lambda x: ((x.city or "").lower(), x.name.lower()))
    return items


def get_organization_detail(
    session: Session, current_user: User, organization_id: int
) -> Organization:
    org = session.get(Organization, organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacija nije pronadjena",
        )

    if current_user.role in (UserRole.admin, UserRole.owner):
        allowed = set(get_user_accessible_org_ids(session, current_user))
        if organization_id not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nemate pristup ovoj organizaciji",
            )
    elif not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacija nije dostupna",
        )

    ensure_organization_default_hours(session, organization_id)
    session.refresh(org)
    return org


def update_organization(
    session: Session,
    current_user: User,
    organization_id: int,
    update_data: OrganizationUpdate,
) -> Organization:
    if current_user.role not in (UserRole.admin, UserRole.owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Potrebne su staff ovlasti",
        )
    org = get_organization_detail(session, current_user, organization_id)
    payload = update_data.model_dump(exclude_unset=True, exclude={"working_hours"})
    working_hours = update_data.working_hours

    if "name" in payload:
        name_value = payload["name"]
        if name_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Naziv organizacije je obavezan",
            )
        normalized_name = name_value.strip()
        if not normalized_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Naziv organizacije je obavezan",
            )
        existing = session.exec(
            select(Organization).where(
                Organization.name == normalized_name,
                Organization.id != organization_id,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organizacija s tim nazivom vec postoji",
            )
        payload["name"] = normalized_name

    for key, value in payload.items():
        setattr(org, key, value)
    session.add(org)

    if working_hours is not None:
        seen_days: set[int] = set()
        for row in working_hours:
            if row.day_of_week in seen_days:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplikat dana u radnom vremenu: {row.day_of_week}",
                )
            seen_days.add(row.day_of_week)

        by_day = {
            h.day_of_week: h
            for h in session.exec(
                select(OrganizationWorkingHour).where(
                    OrganizationWorkingHour.organization_id == organization_id
                )
            ).all()
        }
        for row in working_hours:
            current = by_day.get(row.day_of_week)
            if not current:
                current = OrganizationWorkingHour(
                    organization_id=organization_id,
                    day_of_week=row.day_of_week,
                )
            current.is_closed = row.is_closed
            current.open_time = row.open_time
            current.close_time = row.close_time
            session.add(current)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raw = str(exc.orig).lower() if exc.orig else str(exc).lower()
        if "unique" in raw and "organizations.name" in raw:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organizacija s tim nazivom vec postoji",
            ) from exc
        if "uq_org_working_hours_org_day" in raw or (
            "organization_working_hours.organization_id" in raw
            and "organization_working_hours.day_of_week" in raw
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Neuspjelo spremanje radnog vremena organizacije.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Neuspjelo spremanje organizacije zbog neispravnih podataka.",
        ) from exc
    session.refresh(org)
    ensure_organization_default_hours(session, organization_id)
    session.refresh(org)
    return org


def set_favorite(session: Session, current_user: User, organization_id: int) -> None:
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Favoriti su dostupni samo studentima",
        )
    org = session.get(Organization, organization_id)
    if not org or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacija nije pronadjena",
        )
    existing = session.exec(
        select(UserFavoriteOrganization).where(
            UserFavoriteOrganization.user_id == current_user.id,
            UserFavoriteOrganization.organization_id == organization_id,
        )
    ).first()
    if existing:
        return
    session.add(
        UserFavoriteOrganization(
            user_id=current_user.id,
            organization_id=organization_id,
        )
    )
    session.commit()


def remove_favorite(session: Session, current_user: User, organization_id: int) -> None:
    favorite = session.exec(
        select(UserFavoriteOrganization).where(
            UserFavoriteOrganization.user_id == current_user.id,
            UserFavoriteOrganization.organization_id == organization_id,
        )
    ).first()
    if not favorite:
        return
    session.delete(favorite)
    session.commit()


def get_favorite_organization_ids(session: Session, current_user: User) -> list[int]:
    return session.exec(
        select(UserFavoriteOrganization.organization_id).where(
            UserFavoriteOrganization.user_id == current_user.id
        )
    ).all()


def assert_organization_orderable_now(session: Session, organization_id: int) -> None:
    org = session.get(Organization, organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizacija nije pronadjena",
        )
    ensure_organization_default_hours(session, organization_id)
    session.refresh(org)
    now = datetime.now()
    can_order, reason = _get_orderability(org, now)
    if not can_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason
            or (
                "Narudzba trenutno nije moguca. "
                f"Narudzbe su dopustene do {ORDER_CUTOFF_MINUTES} minuta prije zatvaranja."
            ),
        )


def is_item_orderable_for_org_now(
    session: Session, organization_id: int, base_available: bool
) -> bool:
    if not base_available:
        return False
    org = session.get(Organization, organization_id)
    if not org:
        return False
    ensure_organization_default_hours(session, organization_id)
    session.refresh(org)
    return _is_order_allowed_now(org, datetime.now())
