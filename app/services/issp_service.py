"""ISSP SRCE API integration service.

This module provides integration with the ISSP SRCE (Information System of Student Cards)
API for fetching student card data. The implementation is based on the official API
documentation available at https://isspapi.issp.srce.hr/index.html

Reference implementation: https://github.com/mzo-srce/restoran-klijent (MIT License)

The service handles:
- Authentication with ISSP SRCE API
- Fetching student card information
- Error handling and fallback scenarios
- Data mapping to internal schema
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel

from app.config import settings
from app.schemas import StudentCardInfo

logger = logging.getLogger(__name__)


def is_issp_enabled() -> bool:
    """Check if ISSP service is enabled and configured.

    This checks the configuration at runtime to determine if ISSP
    integration is properly configured with client credentials.

    Returns:
        True if ISSP is properly configured, False otherwise.
    """
    return bool(settings.ISSP_CLIENT_ID and settings.ISSP_CLIENT_SECRET)


class StudentCardData(BaseModel):
    """Normalized student card data from ISSP SRCE API.

    This schema represents the enriched student information
    that can be obtained from the ISSP SRCE system.
    """

    first_name: str | None = None
    last_name: str | None = None
    student_status: str | None = None  # e.g., "active", "inactive", "expired"
    faculty: str | None = None
    validity_status: str | None = None  # e.g., "valid", "expired"
    card_number: str | None = None
    esi: str | None = None
    subsidy_remaining: float | None = None
    profile_image_url: str | None = None
    meal_rights: dict | None = None  # Additional meal rights/subsidies if available
    source: str = "issp"


class ISSPService(ABC):
    """Abstract base class for ISSP SRCE API integration.

    This defines the interface for student card information retrieval.
    """

    @abstractmethod
    def get_card_info(self, card_number: str, esi: str) -> StudentCardInfo:
        """Fetch student card information from ISSP SRCE.

        Args:
            card_number: Student card number
            esi: Student ESI number

        Returns:
            StudentCardInfo with student data

        Raises:
            NotImplementedError: If service is not implemented
            ISSPServiceError: If API call fails
        """
        raise NotImplementedError

    @abstractmethod
    def get_student_card_data(self, student_identifier: str) -> StudentCardData | None:
        """Fetch comprehensive student card data from ISSP SRCE.

        This is the primary method for enriching student information
        with data from the ISSP SRCE system.

        Args:
            student_identifier: Student identifier (card number or ESI)

        Returns:
            StudentCardData with normalized student information,
            or None if student not found or service unavailable

        Raises:
            ISSPServiceError: If API call fails
        """
        raise NotImplementedError


class ISSPServiceError(Exception):
    """Custom exception for ISSP service errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ISSPAPIConfig:
    """Configuration for ISSP SRCE API.

    In production, these values should be configured via environment variables.
    The API base URL and credentials are provided by ISSP SRCE.
    """

    # Production API base URL (from official documentation)
    BASE_URL = "https://isspapi.issp.srce.hr/api"

    # API version
    API_VERSION = "v1"

    # Timeout settings
    TIMEOUT_SECONDS = 30

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 1

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ):
        self.client_id = client_id or settings.ISSP_CLIENT_ID
        self.client_secret = client_secret or settings.ISSP_CLIENT_SECRET
        self.base_url = base_url or settings.ISSP_API_BASE_URL or self.BASE_URL

    @property
    def is_configured(self) -> bool:
        """Check if ISSP API is properly configured."""
        return bool(self.client_id and self.client_secret)


class ISSPAccessToken:
    """Manages ISSP API access token with caching."""

    def __init__(self):
        self._token: str | None = None
        self._expires_at: datetime | None = None

    def is_valid(self) -> bool:
        """Check if current token is still valid."""
        if not self._token or not self._expires_at:
            return False
        # Add 5 minute buffer before actual expiration
        return datetime.utcnow() < (self._expires_at - timedelta(minutes=5))

    def set(self, token: str, expires_in: int):
        """Set new token with expiration."""
        self._token = token
        self._expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    @property
    def token(self) -> str | None:
        return self._token


# Global token cache
_access_token = ISSPAccessToken()


class RealISSPService(ISSPService):
    """Production implementation of ISSP SRCE API integration.

    This service communicates with the official ISSP SRCE API to fetch
    student card information. It handles authentication, error handling,
    and data mapping.

    API Documentation: https://isspapi.issp.srce.hr/index.html
    """

    def __init__(self, config: ISSPAPIConfig | None = None):
        self.config = config or ISSPAPIConfig()

    def _get_access_token(self) -> str:
        """Obtain or refresh access token.

        Returns:
            Valid access token string

        Raises:
            ISSPServiceError: If token cannot be obtained
        """
        global _access_token

        if _access_token.is_valid():
            return _access_token.token

        if not self.config.is_configured:
            raise ISSPServiceError(
                "ISSP API nije konfiguriran. Postavite ISSP_CLIENT_ID i ISSP_CLIENT_SECRET.",
                status_code=500,
            )

        try:
            # Request new token using client credentials flow
            token_url = f"{self.config.base_url}/auth/token"

            with httpx.Client(timeout=self.config.TIMEOUT_SECONDS) as client:
                response = client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code != 200:
                    raise ISSPServiceError(
                        f"Neuspjela autentifikacija na ISSP API: {response.status_code}",
                        status_code=response.status_code,
                    )

                token_data = response.json()
                access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)

                if not access_token:
                    raise ISSPServiceError("ISSP API nije vratio access_token")

                _access_token.set(access_token, expires_in)
                return access_token

        except httpx.TimeoutException as e:
            raise ISSPServiceError(
                "Vremensko ograničenje pri dohvatu tokena", status_code=504
            ) from e
        except httpx.RequestError as e:
            raise ISSPServiceError(f"Greška pri spajanju na ISSP API: {str(e)}") from e

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict:
        """Make authenticated request to ISSP API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON body data

        Returns:
            JSON response as dictionary

        Raises:
            ISSPServiceError: If request fails
        """
        url = f"{self.config.base_url}/{self.config.API_VERSION}/{endpoint}"
        token = self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        for attempt in range(self.config.MAX_RETRIES):
            try:
                with httpx.Client(timeout=self.config.TIMEOUT_SECONDS) as client:
                    response = client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=json_data,
                    )

                    if response.status_code == 401:
                        # Token might be expired, clear and retry once
                        _access_token._token = None
                        _access_token._expires_at = None
                        if attempt == 0:
                            continue
                        raise ISSPServiceError(
                            "Neispravan ili istekao token", status_code=401
                        )

                    if response.status_code == 404:
                        raise ISSPServiceError("Student nije pronađen", status_code=404)

                    if response.status_code >= 500:
                        raise ISSPServiceError(
                            f"Interna greška ISSP API-ja: {response.status_code}",
                            status_code=response.status_code,
                        )

                    if response.status_code not in (200, 201):
                        raise ISSPServiceError(
                            f"Neočekivani odgovor ISSP API-ja: {response.status_code}",
                            status_code=response.status_code,
                        )

                    return response.json()

            except httpx.TimeoutException:
                if attempt == self.config.MAX_RETRIES - 1:
                    raise ISSPServiceError(
                        "Vremensko ograničenje pri zahtjevu", status_code=504
                    ) from None
            except httpx.RequestError as e:
                if attempt == self.config.MAX_RETRIES - 1:
                    raise ISSPServiceError(f"Greška pri zahtjevu: {str(e)}") from e

    def get_card_info(self, card_number: str, esi: str) -> StudentCardInfo:
        """Fetch student card information from ISSP SRCE API.

        This method queries the ISSP API to retrieve student information
        based on card number and ESI.

        Args:
            card_number: Student card number (broj iskaznice)
            esi: Student ESI number

        Returns:
            StudentCardInfo with mapped student data

        Raises:
            ISSPServiceError: If API call fails or student not found
        """
        if not self.config.is_configured:
            raise ISSPServiceError(
                "ISSP integracija nije dostupna. Kontaktirajte administratora.",
                status_code=501,
            )

        try:
            # Query student by card number
            # API endpoint based on official documentation
            endpoint = "students/card"
            params = {
                "cardNumber": card_number.strip(),
                "esi": esi.strip(),
            }

            data = self._make_request("GET", endpoint, params=params)

            # Map API response to our schema
            # The actual field names depend on the ISSP API response format
            # Based on reference implementation and API docs
            full_name = None
            first_name = None
            last_name = None
            faculty = None
            profile_image_url = None
            if data:
                # Try common field name patterns
                full_name = (
                    data.get("fullName")
                    or data.get("full_name")
                    or data.get("imePrezime")
                    or data.get("ime_i_prezime")
                    or f"{data.get('ime', '')} {data.get('prezime', '')}".strip()
                    or None
                )
                first_name = (
                    data.get("firstName")
                    or data.get("first_name")
                    or data.get("ime")
                    or None
                )
                last_name = (
                    data.get("lastName")
                    or data.get("last_name")
                    or data.get("prezime")
                    or None
                )
                faculty = (
                    data.get("faculty")
                    or data.get("fakultet")
                    or data.get("institution")
                    or data.get("ustanova")
                    or None
                )
                profile_image_url = (
                    data.get("profileImageUrl")
                    or data.get("profile_image_url")
                    or data.get("photoUrl")
                    or data.get("photo_url")
                    or data.get("imageUrl")
                    or data.get("image_url")
                    or data.get("slika")
                    or None
                )
            if full_name and (not first_name or not last_name):
                parts = full_name.split(maxsplit=1)
                if parts and not first_name:
                    first_name = parts[0]
                if len(parts) > 1 and not last_name:
                    last_name = parts[1]

            # Get subsidy remaining if available
            subsidy_remaining = data.get("subsidyRemaining") or data.get(
                "subsidy_remaining"
            )
            if subsidy_remaining is not None:
                try:
                    subsidy_remaining = float(subsidy_remaining)
                except (ValueError, TypeError):
                    subsidy_remaining = None

            return StudentCardInfo(
                card_number=card_number.strip(),
                esi=esi.strip(),
                full_name=full_name,
                first_name=first_name,
                last_name=last_name,
                faculty=faculty,
                profile_image_url=profile_image_url,
                subsidy_remaining=subsidy_remaining,
                source="issp",
            )

        except ISSPServiceError:
            raise
        except Exception as e:
            logger.error(f"Neočekivana greška pri dohvatu ISSP podataka: {str(e)}")
            raise ISSPServiceError(
                f"Greška pri dohvatu podataka s iskaznice: {str(e)}"
            ) from e

    def get_student_card_data(self, student_identifier: str) -> StudentCardData | None:
        """Fetch comprehensive student card data from ISSP SRCE API.

        This method queries the ISSP API to retrieve detailed student information
        including status, faculty, and meal rights.

        Args:
            student_identifier: Student identifier (card number or ESI)

        Returns:
            StudentCardData with normalized student information,
            or None if student not found or service unavailable

        Raises:
            ISSPServiceError: If API call fails
        """
        if not self.config.is_configured:
            logger.warning(
                "ISSP API nije konfiguriran - preskačem dohvat podataka o studentu"
            )
            return None

        try:
            # Determine if identifier is card number or ESI based on format
            identifier = student_identifier.strip()

            # Query student by identifier
            endpoint = "students/lookup"
            params = {"identifier": identifier}

            data = self._make_request("GET", endpoint, params=params)

            if not data:
                return None

            # Parse name fields
            first_name = None
            last_name = None
            full_name = (
                data.get("fullName")
                or data.get("full_name")
                or data.get("imePrezime")
                or data.get("ime_i_prezime")
                or ""
            )
            if full_name:
                parts = full_name.split(maxsplit=1)
                if len(parts) >= 1:
                    first_name = parts[0]
                if len(parts) >= 2:
                    last_name = parts[1]
            else:
                first_name = data.get("ime")
                last_name = data.get("prezime")

            # Student status
            student_status = (
                data.get("studentStatus")
                or data.get("student_status")
                or data.get("status")
            )

            # Faculty
            faculty = (
                data.get("faculty")
                or data.get("fakultet")
                or data.get("institution")
                or data.get("ustanova")
            )

            # Validity status
            validity_status = (
                data.get("validityStatus")
                or data.get("validity_status")
                or data.get("validUntil")
                or data.get("valid_until")
            )

            # Subsidy remaining
            subsidy_remaining = data.get("subsidyRemaining") or data.get(
                "subsidy_remaining"
            )
            if subsidy_remaining is not None:
                try:
                    subsidy_remaining = float(subsidy_remaining)
                except (ValueError, TypeError):
                    subsidy_remaining = None

            # Meal rights
            meal_rights = data.get("mealRights") or data.get("meal_rights")
            profile_image_url = (
                data.get("profileImageUrl")
                or data.get("profile_image_url")
                or data.get("photoUrl")
                or data.get("photo_url")
                or data.get("imageUrl")
                or data.get("image_url")
                or data.get("slika")
            )

            return StudentCardData(
                first_name=first_name,
                last_name=last_name,
                student_status=student_status,
                faculty=faculty,
                validity_status=validity_status,
                card_number=data.get("cardNumber") or data.get("card_number"),
                esi=data.get("esi"),
                subsidy_remaining=subsidy_remaining,
                profile_image_url=profile_image_url,
                meal_rights=meal_rights,
                source="issp",
            )

        except ISSPServiceError as e:
            if e.status_code == 404:
                logger.info(
                    f"Student nije pronađen u ISSP sustavu: {student_identifier}"
                )
                return None
            raise
        except Exception as e:
            logger.error(
                f"Neočekivana greška pri dohvatu podataka o studentu: {str(e)}"
            )
            return None


class NotImplementedISSPService(ISSPService):
    """Stub implementation for development/testing without ISSP credentials."""

    def get_card_info(self, card_number: str, esi: str) -> StudentCardInfo:
        """Return stub response indicating ISSP is not configured."""
        raise NotImplementedError(
            "ISSP integracija nije konfigurirana. "
            "Postavite ISSP_CLIENT_ID i ISSP_CLIENT_SECRET environment varijable."
        )

    def get_student_card_data(self, student_identifier: str) -> StudentCardData | None:
        """Return None when ISSP is not configured (graceful degradation).

        The system must continue working without ISSP API availability.
        """
        logger.warning(
            "ISSP integracija nije konfigurirana - sustav radi bez ISSP enrichmenta. "
            "Postavite ISSP_CLIENT_ID i ISSP_CLIENT_SECRET za punu funkcionalnost."
        )
        return None


def get_issp_service() -> ISSPService:
    """Factory function to get appropriate ISSP service instance.

    Returns RealISSPService if configured, otherwise NotImplementedISSPService.
    """
    config = ISSPAPIConfig()
    if config.is_configured:
        return RealISSPService(config)
    return NotImplementedISSPService()
