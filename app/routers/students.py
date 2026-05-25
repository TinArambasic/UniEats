from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import User, UserRole
from app.schemas import ISSPLinkRequest, StudentCardInfo
from app.services.issp_service import (
    ISSPService,
    ISSPServiceError,
    get_issp_service,
    is_issp_enabled,
)
from app.validators import validate_student_card_number

router = APIRouter(prefix="/students", tags=["Student card"])

_ISSP_NOT_CONFIGURED_RESPONSE = {
    "success": False,
    "error": "ISSP_NOT_CONFIGURED",
    "message": (
        "Studentska iskaznica nije dostupna: ISSP integracija nije konfigurirana na backendu. "
        "Povezivanje je spremno i aktivira se nakon unosa ISSP pristupnih podataka."
    ),
}

_CARD_KEYS = (
    "card_number",
    "cardnumber",
    "broj_kartice",
    "brojkartice",
    "card",
    "broj",
)
_ESI_KEYS = ("esi", "student_esi")


def _issp_not_configured_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=_ISSP_NOT_CONFIGURED_RESPONSE,
    )


def _extract_field(mapping: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    normalized = {str(k).strip().lower(): v for k, v in mapping.items()}
    for key in keys:
        value = normalized.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_link_credentials(card_number: str, esi: str) -> tuple[str, str]:
    validated_card = validate_student_card_number(card_number)
    normalized_esi = str(esi).strip()
    if not normalized_esi:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ESI broj je obavezan.",
        )
    return validated_card, normalized_esi


def _parse_issp_qr_payload(payload: str) -> tuple[str, str]:
    raw = (payload or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR payload je prazan.",
        )

    def maybe_return(card: str | None, esi: str | None) -> tuple[str, str] | None:
        if not card or not esi:
            return None
        return _normalize_link_credentials(card, esi)

    # JSON payload
    try:
        parsed_json = json.loads(raw)
        if isinstance(parsed_json, dict):
            pair = maybe_return(
                _extract_field(parsed_json, _CARD_KEYS),
                _extract_field(parsed_json, _ESI_KEYS),
            )
            if pair:
                return pair
    except json.JSONDecodeError:
        pass

    # URL payload with query params
    parsed_url = urlparse(raw)
    if parsed_url.query:
        query = {
            k.lower(): (v[0] if v else "")
            for k, v in parse_qs(parsed_url.query).items()
        }
        pair = maybe_return(
            _extract_field(query, _CARD_KEYS),
            _extract_field(query, _ESI_KEYS),
        )
        if pair:
            return pair

    # Raw query string payload
    if "=" in raw and ("&" in raw or ";" in raw):
        query = {
            k.lower(): (v[0] if v else "")
            for k, v in parse_qs(raw.replace(";", "&")).items()
        }
        pair = maybe_return(
            _extract_field(query, _CARD_KEYS),
            _extract_field(query, _ESI_KEYS),
        )
        if pair:
            return pair

    # Key-value text payload (e.g. "card_number:12345 esi:ESI1")
    key_value_pairs = dict(
        (k.strip().lower(), v.strip())
        for k, v in re.findall(r"([A-Za-z_]+)\s*[:=]\s*([^\s;|,]+)", raw)
    )
    if key_value_pairs:
        pair = maybe_return(
            _extract_field(key_value_pairs, _CARD_KEYS),
            _extract_field(key_value_pairs, _ESI_KEYS),
        )
        if pair:
            return pair

    # Heuristic fallback
    card_match = re.search(r"\b\d{6,32}\b", raw)
    esi_match = re.search(r"\bESI[A-Za-z0-9_-]*\b", raw, flags=re.IGNORECASE)
    pair = maybe_return(
        card_match.group(0) if card_match else None,
        esi_match.group(0) if esi_match else None,
    )
    if pair:
        return pair

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "QR zapis ne sadrži prepoznatljive card_number i esi vrijednosti. "
            "Podržani formati su JSON ili query string."
        ),
    )


def _require_issp_enabled() -> JSONResponse | None:
    if not is_issp_enabled():
        return _issp_not_configured_response()
    return None


def _fetch_card_info(
    issp_service: ISSPService,
    card_number: str,
    esi: str,
) -> StudentCardInfo:
    try:
        return issp_service.get_card_info(card_number, esi)
    except ISSPServiceError as exc:
        if exc.status_code == 501 or exc.status_code is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_ISSP_NOT_CONFIGURED_RESPONSE["message"],
            ) from exc
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_ISSP_NOT_CONFIGURED_RESPONSE["message"],
        ) from exc


def _ensure_unique_student_credentials(
    session: Session,
    current_user: User,
    card_number: str,
    esi: str,
) -> None:
    existing_card_user = session.exec(
        select(User).where(
            User.student_card_number == card_number, User.id != current_user.id
        )
    ).first()
    if existing_card_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Broj studentske iskaznice je već povezan s drugim korisnikom.",
        )

    existing_esi_user = session.exec(
        select(User).where(User.student_esi == esi, User.id != current_user.id)
    ).first()
    if existing_esi_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ESI broj je već povezan s drugim korisnikom.",
        )


def _apply_issp_info_to_user(
    session: Session,
    current_user: User,
    info: StudentCardInfo,
    *,
    linked_card_number: str | None = None,
    linked_esi: str | None = None,
) -> None:
    updated = False

    if linked_card_number and current_user.student_card_number != linked_card_number:
        current_user.student_card_number = linked_card_number
        updated = True
    if linked_esi and current_user.student_esi != linked_esi:
        current_user.student_esi = linked_esi
        updated = True

    if (
        info.subsidy_remaining is not None
        and current_user.subsidy_remaining != info.subsidy_remaining
    ):
        current_user.subsidy_remaining = info.subsidy_remaining
        updated = True

    resolved_first_name = (info.first_name or "").strip() or None
    resolved_last_name = (info.last_name or "").strip() or None
    if (not resolved_first_name or not resolved_last_name) and info.full_name:
        parts = info.full_name.split(maxsplit=1)
        if parts and not resolved_first_name:
            resolved_first_name = parts[0].strip() or None
        if len(parts) > 1 and not resolved_last_name:
            resolved_last_name = parts[1].strip() or None

    if resolved_first_name and current_user.first_name != resolved_first_name:
        current_user.first_name = resolved_first_name
        updated = True
    if resolved_last_name and current_user.last_name != resolved_last_name:
        current_user.last_name = resolved_last_name
        updated = True

    resolved_profile_image = (info.profile_image_url or "").strip() or None
    if (
        resolved_profile_image
        and current_user.profile_image_url != resolved_profile_image
    ):
        current_user.profile_image_url = resolved_profile_image
        updated = True

    if updated:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)


@router.get(
    "/status",
    summary="Provjeri status ISSP integracije",
    responses={
        200: {
            "description": "Status ISSP integracije",
            "content": {
                "application/json": {
                    "example": {
                        "enabled": True,
                        "message": "ISSP integracija je dostupna.",
                    }
                }
            },
        },
    },
)
def get_issp_status():
    enabled = is_issp_enabled()
    return {
        "enabled": enabled,
        "message": (
            "ISSP integracija je dostupna."
            if enabled
            else "ISSP backend nije konfiguriran."
        ),
    }


@router.get("/issp/status", include_in_schema=False)
def get_issp_status_legacy_alias():
    return get_issp_status()


@router.get(
    "/card-info",
    response_model=StudentCardInfo,
    summary="Dohvat podataka sa studentske iskaznice (koristi pohranjene podatke korisnika)",
)
def get_card_info(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    issp_service: ISSPService = Depends(get_issp_service),
):
    if not current_user.student_card_number or not current_user.student_esi:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Korisnik nema povezane ISSP podatke (broj kartice i ESI).",
        )

    disabled = _require_issp_enabled()
    if disabled:
        return disabled

    info = _fetch_card_info(
        issp_service,
        current_user.student_card_number,
        current_user.student_esi,
    )
    _apply_issp_info_to_user(session, current_user, info)
    return info


@router.post(
    "/issp/link",
    response_model=StudentCardInfo,
    summary="Poveži ISSP račun (ESI + kartica ili QR payload)",
)
def link_issp_account(
    payload: ISSPLinkRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    issp_service: ISSPService = Depends(get_issp_service),
):
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ISSP povezivanje je dostupno samo studentima.",
        )

    disabled = _require_issp_enabled()
    if disabled:
        return disabled

    if payload.method == "manual":
        card_number, esi = _normalize_link_credentials(
            payload.card_number or "", payload.esi or ""
        )
    else:
        card_number, esi = _parse_issp_qr_payload(payload.qr_payload or "")

    _ensure_unique_student_credentials(session, current_user, card_number, esi)
    info = _fetch_card_info(issp_service, card_number, esi)
    _apply_issp_info_to_user(
        session,
        current_user,
        info,
        linked_card_number=card_number,
        linked_esi=esi,
    )
    return info


@router.post(
    "/issp/sync",
    response_model=StudentCardInfo,
    summary="Osvježi ISSP podatke za povezani račun",
)
def sync_issp_account(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    issp_service: ISSPService = Depends(get_issp_service),
):
    return get_card_info(
        session=session,
        current_user=current_user,
        issp_service=issp_service,
    )


@router.post(
    "/card-lookup",
    response_model=StudentCardInfo,
    summary="Dohvat podataka sa studentske iskaznice (proizvoljni unos)",
    responses={
        400: {"description": "Nedostaju obavezni podaci (broj iskaznice ili ESI)"},
        503: {"description": "ISSP usluga nije konfigurirana"},
    },
)
@router.get("/card-lookup", include_in_schema=False)
def lookup_card(
    card_number: str = Query(
        ..., min_length=1, description="Broj studentske iskaznice"
    ),
    esi: str = Query(..., min_length=1, description="ESI broj studenta"),
    issp_service: ISSPService = Depends(get_issp_service),
):
    disabled = _require_issp_enabled()
    if disabled:
        return disabled

    validated_card_number, normalized_esi = _normalize_link_credentials(
        card_number, esi
    )
    return _fetch_card_info(issp_service, validated_card_number, normalized_esi)
