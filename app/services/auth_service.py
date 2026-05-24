from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.auth import get_password_hash, verify_password
from app.config import settings
from app.logging import log_event
from app.models import (
    LoginAudit,
    Organization,
    User,
    UserOrganization,
    UserRole,
)
from app.schemas import (
    AdminCreate,
    UserCreate,
    UserProfileUpdate,
)
from app.services.rate_limiter import RateLimiterUnavailable, get_rate_limiter
from app.validators import validate_student_card_number

GENERIC_STUDENT_LOGIN_ERROR = "Pogresan broj kartice ili lozinka"
GENERIC_STAFF_LOGIN_ERROR = "Pogresno korisničko ime ili lozinka"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _ensure_unique_email(
    session: Session, email: str, *, ignore_user_id: int | None = None
) -> None:
    stmt = select(User).where(User.email == email)
    if ignore_user_id is not None:
        stmt = stmt.where(User.id != ignore_user_id)
    if session.exec(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email adresa je vec registrirana",
        )


def _normalize_organization_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Naziv organizacije je obavezan",
        )
    return normalized


def get_or_create_organization(session: Session, name: str) -> Organization:
    normalized_name = _normalize_organization_name(name)
    existing = session.exec(
        select(Organization).where(Organization.name == normalized_name)
    ).first()
    if existing:
        return existing

    organization = Organization(name=normalized_name, is_active=True)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


def get_or_create_default_organization(session: Session) -> Organization:
    return get_or_create_organization(session, settings.DEFAULT_ORGANIZATION_NAME)


def _require_primary_organization_id(user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Korisnik nema pridruzenu organizaciju",
        )
    return user.organization_id


def _resolve_primary_organization_id(session: Session, user: User) -> int:
    if user.organization_id is not None:
        return user.organization_id

    membership_ids = session.exec(
        select(UserOrganization.organization_id)
        .where(UserOrganization.user_id == user.id)
        .order_by(UserOrganization.organization_id.asc())
    ).all()
    if not membership_ids:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Korisnik nema pridruzenu organizaciju",
        )

    primary_org_id = int(membership_ids[0])
    user.organization_id = primary_org_id
    session.add(user)
    session.commit()
    session.refresh(user)
    return primary_org_id


def _ensure_membership(session: Session, user_id: int, organization_id: int) -> None:
    existing = session.exec(
        select(UserOrganization).where(
            UserOrganization.user_id == user_id,
            UserOrganization.organization_id == organization_id,
        )
    ).first()
    if existing:
        return
    session.add(UserOrganization(user_id=user_id, organization_id=organization_id))
    session.commit()


def _replace_memberships(
    session: Session, user: User, organization_ids: Iterable[int]
) -> None:
    unique_ids = sorted(set(int(org_id) for org_id in organization_ids))
    if not unique_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Korisnik mora imati barem jednu organizaciju",
        )

    organizations = session.exec(
        select(Organization).where(Organization.id.in_(unique_ids))
    ).all()
    existing_ids = {org.id for org in organizations if org.id is not None}
    missing = [oid for oid in unique_ids if oid not in existing_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organizacije nisu pronadjene: {missing}",
        )

    existing_links = session.exec(
        select(UserOrganization).where(UserOrganization.user_id == user.id)
    ).all()
    existing_set = {link.organization_id for link in existing_links}
    new_set = set(unique_ids)

    for link in existing_links:
        if link.organization_id not in new_set:
            session.delete(link)
    for org_id in new_set:
        if org_id not in existing_set:
            session.add(UserOrganization(user_id=user.id, organization_id=org_id))

    user.organization_id = unique_ids[0]
    session.add(user)
    session.commit()
    session.refresh(user)


def ensure_user_membership(session: Session, user: User) -> None:
    primary_org_id = _resolve_primary_organization_id(session, user)
    _ensure_membership(session, user.id, primary_org_id)


def get_user_accessible_org_ids(session: Session, user: User) -> list[int]:
    stmt = select(UserOrganization.organization_id).where(
        UserOrganization.user_id == user.id
    )
    ids = set(session.exec(stmt).all())
    if user.organization_id is not None:
        ids.add(user.organization_id)
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Korisnik nema pridruzene organizacije",
        )
    return sorted(ids)


def count_owner_users(session: Session, organization_id: int | None = None) -> int:
    stmt = select(User.id).where(User.role == UserRole.owner)
    if organization_id is not None:
        stmt = stmt.where(User.organization_id == organization_id)
    return len(session.exec(stmt).all())


def register_user(session: Session, user_data: UserCreate) -> User:
    email = _normalize_email(str(user_data.email))
    organization = get_or_create_default_organization(session)

    if session.exec(
        select(User).where(User.student_card_number == user_data.student_card_number)
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Broj kartice je vec registriran",
        )
    if session.exec(
        select(User).where(User.student_esi == user_data.student_esi)
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ESI broj je vec registriran",
        )
    _ensure_unique_email(session, email)

    user = User(
        organization_id=organization.id,
        email=email,
        hashed_password=get_password_hash(user_data.password),
        role=UserRole.student,
        student_card_number=user_data.student_card_number,
        student_esi=user_data.student_esi,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _ensure_membership(session, user.id, organization.id)
    session.refresh(user)
    return user


def _ensure_unique_username(
    session: Session, username: str, *, ignore_user_id: int | None = None
) -> None:
    """Ensure username is unique across all users."""
    stmt = select(User).where(User.username == username)
    if ignore_user_id is not None:
        stmt = stmt.where(User.id != ignore_user_id)
    if session.exec(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Korisničko ime je već zauzeto",
        )


def _ensure_unique_oib(
    session: Session, oib: str, *, ignore_user_id: int | None = None
) -> None:
    """Ensure OIB is unique across all users."""
    stmt = select(User).where(User.oib == oib)
    if ignore_user_id is not None:
        stmt = stmt.where(User.id != ignore_user_id)
    if session.exec(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIB je već registriran",
        )


def create_admin_user(
    session: Session, owner_user: User, admin_data: AdminCreate
) -> User:
    """Create a new admin/staff user.

    Staff users authenticate using username + password (not email).
    Required fields: username (unique), oib (unique), password, first_name, last_name.
    """
    if owner_user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Samo admin organizacije moze kreirati djelatnike",
        )

    username = admin_data.username.strip().lower()
    oib = admin_data.oib.strip()

    # Validate uniqueness of username and OIB
    _ensure_unique_username(session, username)
    _ensure_unique_oib(session, oib)

    default_org_id = _require_primary_organization_id(owner_user)
    org_ids = admin_data.organization_ids or [default_org_id]
    org_ids = sorted(set(int(v) for v in org_ids))
    organizations = session.exec(
        select(Organization).where(Organization.id.in_(org_ids))
    ).all()
    if len(organizations) != len(org_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jedna ili vise organizacija ne postoje",
        )

    user = User(
        organization_id=org_ids[0],
        username=username,
        oib=oib,
        hashed_password=get_password_hash(admin_data.password),
        role=UserRole.admin,
        student_card_number=None,
        student_esi=None,
        first_name=admin_data.first_name,
        last_name=admin_data.last_name,
        is_active=True,
        email=None,  # Staff users don't use email
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _replace_memberships(session, user, org_ids)
    session.refresh(user)
    return user


def create_owner_user(
    session: Session,
    username: str,
    password: str,
    organization_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
) -> User:
    """Create a new owner user.

    Owner users authenticate using username (not email).
    Email is optional metadata only.

    Args:
        username: Unique username for authentication (required)
        password: Password (required)
        organization_name: Organization name (optional)
        first_name: First name (optional)
        last_name: Last name (optional)
        email: Email address for metadata only, not used for login (optional)
    """
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lozinka owner korisnika mora imati najmanje 6 znakova",
        )

    # Normalize and validate username
    normalized_username = username.strip().lower()
    _ensure_unique_username(session, normalized_username)

    # Handle optional email
    normalized_email = _normalize_email(email) if email else None
    if normalized_email:
        _ensure_unique_email(session, normalized_email)

    org_name = organization_name or settings.DEFAULT_ORGANIZATION_NAME
    organization = get_or_create_organization(session, org_name)
    owner = User(
        organization_id=organization.id,
        email=normalized_email,
        username=normalized_username,
        hashed_password=get_password_hash(password),
        role=UserRole.owner,
        student_card_number=None,
        student_esi=None,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)
    _ensure_membership(session, owner.id, organization.id)
    session.refresh(owner)
    return owner


def _owner_scope_org_ids(session: Session, owner_user: User) -> list[int]:
    if owner_user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Samo owner ima pristup ovoj funkcionalnosti",
        )
    return get_user_accessible_org_ids(session, owner_user)


def list_admin_users(session: Session, owner_user: User) -> list[User]:
    scope_org_ids = _owner_scope_org_ids(session, owner_user)
    stmt = (
        select(User)
        .join(UserOrganization, UserOrganization.user_id == User.id)
        .where(
            User.role == UserRole.admin,
            UserOrganization.organization_id.in_(scope_org_ids),
        )
        .distinct()
        .order_by(User.id.desc())
    )
    return session.exec(stmt).all()


def _get_admin_in_scope(session: Session, owner_user: User, admin_id: int) -> User:
    scope_org_ids = _owner_scope_org_ids(session, owner_user)
    stmt = (
        select(User)
        .join(UserOrganization, UserOrganization.user_id == User.id)
        .where(
            User.id == admin_id,
            User.role == UserRole.admin,
            UserOrganization.organization_id.in_(scope_org_ids),
        )
        .distinct()
    )
    user = session.exec(stmt).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Djelatnik nije pronadjen",
        )
    return user


def update_admin_status(
    session: Session, owner_user: User, admin_id: int, is_active: bool
) -> User:
    user = _get_admin_in_scope(session, owner_user, admin_id)
    user.is_active = is_active
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_admin_user(session: Session, owner_user: User, admin_id: int) -> None:
    user = _get_admin_in_scope(session, owner_user, admin_id)
    links = session.exec(
        select(UserOrganization).where(UserOrganization.user_id == user.id)
    ).all()
    for link in links:
        session.delete(link)
    session.delete(user)
    session.commit()


def set_admin_organizations(
    session: Session, owner_user: User, admin_id: int, organization_ids: list[int]
) -> User:
    admin = _get_admin_in_scope(session, owner_user, admin_id)
    owner_scope = set(_owner_scope_org_ids(session, owner_user))
    target_ids = sorted(set(int(v) for v in organization_ids))
    if not target_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Djelatnik mora imati barem jednu organizaciju",
        )
    if not set(target_ids).issubset(owner_scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mozete dodijeliti samo organizacije kojima imate pristup",
        )
    _replace_memberships(session, admin, target_ids)
    session.refresh(admin)
    return admin


def add_admin_organization(
    session: Session, owner_user: User, admin_id: int, organization_id: int
) -> User:
    admin = _get_admin_in_scope(session, owner_user, admin_id)
    current_ids = get_user_accessible_org_ids(session, admin)
    if organization_id not in current_ids:
        current_ids.append(organization_id)
    return set_admin_organizations(session, owner_user, admin_id, current_ids)


def remove_admin_organization(
    session: Session, owner_user: User, admin_id: int, organization_id: int
) -> User:
    admin = _get_admin_in_scope(session, owner_user, admin_id)
    current_ids = [
        oid
        for oid in get_user_accessible_org_ids(session, admin)
        if oid != organization_id
    ]
    return set_admin_organizations(session, owner_user, admin_id, current_ids)


def move_admin_organization(
    session: Session,
    owner_user: User,
    admin_id: int,
    from_organization_id: int,
    to_organization_id: int,
) -> User:
    admin = _get_admin_in_scope(session, owner_user, admin_id)
    current_ids = get_user_accessible_org_ids(session, admin)
    current_ids = [oid for oid in current_ids if oid != from_organization_id]
    if to_organization_id not in current_ids:
        current_ids.append(to_organization_id)
    return set_admin_organizations(session, owner_user, admin_id, current_ids)


def list_owner_users(session: Session, owner_user: User) -> list[User]:
    scope_org_ids = _owner_scope_org_ids(session, owner_user)
    stmt = (
        select(User)
        .join(UserOrganization, UserOrganization.user_id == User.id)
        .where(
            User.role == UserRole.owner,
            UserOrganization.organization_id.in_(scope_org_ids),
        )
        .distinct()
        .order_by(User.id.desc())
    )
    return session.exec(stmt).all()


def delete_owner_user(session: Session, current_owner: User, owner_id: int) -> None:
    scope_org_ids = _owner_scope_org_ids(session, current_owner)
    stmt = (
        select(User)
        .join(UserOrganization, UserOrganization.user_id == User.id)
        .where(
            User.id == owner_id,
            User.role == UserRole.owner,
            UserOrganization.organization_id.in_(scope_org_ids),
        )
        .distinct()
    )
    user = session.exec(stmt).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin organizacije nije pronadjen",
        )
    if count_owner_users(session) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nije moguce obrisati zadnjeg admina organizacije",
        )
    links = session.exec(
        select(UserOrganization).where(UserOrganization.user_id == user.id)
    ).all()
    for link in links:
        session.delete(link)
    session.delete(user)
    session.commit()


def ensure_owner_presence(session: Session) -> bool:
    return count_owner_users(session) > 0


def seed_owner_if_configured(session: Session) -> None:
    """Seed owner user from environment configuration.

    Owner users authenticate using username (not email).
    If OWNER_EMAIL is configured, it is used as the username for backward compatibility.
    Email is stored as optional metadata only.
    """
    # Use OWNER_EMAIL as the username for backward compatibility
    # In the new design, username is the primary identifier
    config_username = settings.OWNER_EMAIL
    password = settings.OWNER_PASSWORD or ""

    if not config_username or not password:
        return

    # Normalize username (used to be email, now is username)
    normalized_username = _normalize_email(config_username)  # lowercase + strip

    # Check if owner already exists by username
    existing = session.exec(
        select(User).where(User.username == normalized_username)
    ).first()
    if existing:
        if existing.role != UserRole.owner:
            log_event(
                "owner_seed_skipped_existing_user",
                username=normalized_username,
                current_role=existing.role.value,
            )
        else:
            ensure_user_membership(session, existing)
            log_event("owner_seed_already_exists", username=normalized_username)
        return

    # Create owner with username (email is optional metadata)
    create_owner_user(
        session=session,
        username=normalized_username,
        password=password,
        organization_name=settings.OWNER_ORGANIZATION_NAME,
        first_name=settings.OWNER_FIRST_NAME,
        last_name=settings.OWNER_LAST_NAME,
        email=normalized_username,  # Store as metadata only
    )
    log_event("owner_seed_created", username=normalized_username)


def list_organization_users(
    session: Session, current_user: User, organization_id: int | None = None
) -> list[User]:
    accessible_ids = get_user_accessible_org_ids(session, current_user)
    if organization_id is not None:
        selected_org_id = organization_id
    elif current_user.organization_id is not None:
        selected_org_id = current_user.organization_id
    elif accessible_ids:
        selected_org_id = accessible_ids[0]
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Korisnik nema pridruzene organizacije",
        )
    if selected_org_id not in accessible_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nemate pristup trazenoj organizaciji",
        )
    return session.exec(
        select(User)
        .join(UserOrganization, UserOrganization.user_id == User.id)
        .where(UserOrganization.organization_id == selected_org_id)
        .distinct()
        .order_by(User.id.desc())
    ).all()


def update_profile(
    session: Session, current_user: User, update_data: UserProfileUpdate
) -> User:
    payload = update_data.model_dump(exclude_unset=True)
    if "email" in payload and payload["email"] is not None:
        normalized_email = _normalize_email(str(payload["email"]))
        _ensure_unique_email(session, normalized_email, ignore_user_id=current_user.id)
        current_user.email = normalized_email
    if "first_name" in payload:
        current_user.first_name = payload["first_name"]
    if "last_name" in payload:
        current_user.last_name = payload["last_name"]
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    ensure_user_membership(session, current_user)
    session.refresh(current_user)
    return current_user


def update_password(
    session: Session,
    current_user: User,
    current_password: str,
    new_password: str,
) -> User:
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trenutna lozinka nije ispravna",
        )
    if current_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nova lozinka mora biti razlicita od trenutne",
        )
    current_user.hashed_password = get_password_hash(new_password)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


def set_profile_image(session: Session, current_user: User, image_url: str) -> User:
    current_user.profile_image_url = image_url
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


def clear_profile_image(session: Session, current_user: User) -> User:
    current_user.profile_image_url = None
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


def _write_login_audit(
    session: Session,
    card_number: str,
    success: bool,
    ip_address: str | None,
    user_id: int | None = None,
    reason: str | None = None,
) -> None:
    audit = LoginAudit(
        student_card_number=card_number,
        user_id=user_id,
        success=success,
        ip_address=ip_address,
        reason=reason,
    )
    session.add(audit)
    session.commit()


def _check_login_rate_limit(rate_key: str, ip_address: str | None) -> int | None:
    rate_limiter = get_rate_limiter()
    try:
        result = rate_limiter.check(rate_key)
    except RateLimiterUnavailable as exc:
        log_event(
            "rate_limiter_error",
            success=False,
            ip_address=ip_address,
            reason=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter nije dostupan",
        ) from exc

    if result.allowed:
        return None
    return result.retry_after


def authenticate_student_user(
    session: Session,
    card_number: str,
    password: str,
    ip_address: str | None,
) -> User:
    raw_card_number = card_number.strip()
    audit_card_number = (raw_card_number or "unknown")[:32]
    rate_key = f"student:{ip_address or 'unknown'}:{raw_card_number or 'empty'}"
    retry_after = _check_login_rate_limit(rate_key, ip_address)
    if retry_after is not None:
        _write_login_audit(
            session,
            audit_card_number,
            success=False,
            ip_address=ip_address,
            user_id=None,
            reason="rate_limited",
        )
        log_event(
            "login_attempt",
            card_number=audit_card_number,
            success=False,
            ip_address=ip_address,
            reason="rate_limited",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Previse pokusaja prijave. Pokusajte kasnije.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        validated_card_number = validate_student_card_number(raw_card_number)
    except ValueError:
        _write_login_audit(
            session,
            audit_card_number,
            success=False,
            ip_address=ip_address,
            user_id=None,
            reason="invalid_format",
        )
        log_event(
            "login_attempt",
            card_number=audit_card_number,
            success=False,
            ip_address=ip_address,
            reason="invalid_format",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_STUDENT_LOGIN_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = session.exec(
        select(User).where(
            User.student_card_number == validated_card_number,
            User.role == UserRole.student,
        )
    ).first()
    if not user or not verify_password(password, user.hashed_password):
        _write_login_audit(
            session,
            validated_card_number,
            success=False,
            ip_address=ip_address,
            user_id=user.id if user else None,
            reason="invalid_credentials",
        )
        log_event(
            "login_attempt",
            card_number=validated_card_number,
            success=False,
            ip_address=ip_address,
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_STUDENT_LOGIN_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        _write_login_audit(
            session,
            validated_card_number,
            success=False,
            ip_address=ip_address,
            user_id=user.id,
            reason="inactive",
        )
        log_event(
            "login_attempt",
            card_number=validated_card_number,
            success=False,
            ip_address=ip_address,
            reason="inactive",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_STUDENT_LOGIN_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )

    ensure_user_membership(session, user)
    session.refresh(user)

    _write_login_audit(
        session,
        validated_card_number,
        success=True,
        ip_address=ip_address,
        user_id=user.id,
        reason="success",
    )
    log_event(
        "login_attempt",
        card_number=validated_card_number,
        success=True,
        ip_address=ip_address,
        reason="success",
    )
    return user


def authenticate_staff_user(
    session: Session,
    username: str,
    password: str,
    ip_address: str | None,
) -> User:
    """Authenticate staff user (admin/owner) using username and password.

    Staff users log in with their unique username (not email).
    """
    normalized_username = username.strip().lower()
    rate_key = f"staff:{ip_address or 'unknown'}:{normalized_username or 'empty'}"
    retry_after = _check_login_rate_limit(rate_key, ip_address)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Previse pokusaja prijave. Pokusajte kasnije.",
            headers={"Retry-After": str(retry_after)},
        )

    user = session.exec(
        select(User).where(User.username == normalized_username)
    ).first()
    if (
        not user
        or user.role not in (UserRole.admin, UserRole.owner)
        or not verify_password(password, user.hashed_password)
        or not user.is_active
    ):
        log_event(
            "staff_login_attempt",
            username=normalized_username,
            success=False,
            ip_address=ip_address,
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_STAFF_LOGIN_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )

    ensure_user_membership(session, user)
    session.refresh(user)

    log_event(
        "staff_login_attempt",
        username=normalized_username,
        success=True,
        ip_address=ip_address,
        reason="success",
    )
    return user


def authenticate_user(
    session: Session,
    card_number: str,
    password: str,
    ip_address: str | None,
) -> User:
    return authenticate_student_user(session, card_number, password, ip_address)
