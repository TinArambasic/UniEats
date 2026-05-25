import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models import OrderStatus, UserRole
from app.validators import validate_student_card_number

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ---------------------------------------------------------------------------
# Auth / user / organization schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    student_card_number: str
    student_esi: str
    first_name: str | None = None
    last_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Lozinka mora imati najmanje 6 znakova")
        return v

    @field_validator("student_card_number")
    @classmethod
    def student_card_number_valid(cls, v: str) -> str:
        return validate_student_card_number(v)

    @field_validator("student_esi")
    @classmethod
    def student_esi_not_empty(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("ESI broj je obavezan")
        return value


class OrganizationWorkingHourBase(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    is_closed: bool = False
    open_time: str | None = None
    close_time: str | None = None

    @field_validator("open_time", "close_time")
    @classmethod
    def validate_hhmm(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        if not _HHMM_RE.match(value):
            raise ValueError("Vrijeme mora biti u formatu HH:MM")
        return value

    @model_validator(mode="after")
    def validate_closed_and_range(self):
        if self.is_closed:
            self.open_time = None
            self.close_time = None
            return self
        if not self.open_time or not self.close_time:
            raise ValueError("Za otvoreni dan open_time i close_time su obavezni")
        if self.open_time >= self.close_time:
            raise ValueError("open_time mora biti prije close_time")
        return self


class OrganizationWorkingHourUpdate(OrganizationWorkingHourBase):
    pass


class OrganizationWorkingHourRead(OrganizationWorkingHourBase):
    id: int
    organization_id: int

    model_config = {"from_attributes": True}


class OrganizationRead(BaseModel):
    id: int
    name: str
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool
    working_hours: list[OrganizationWorkingHourRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class OrganizationListItem(BaseModel):
    id: int
    name: str
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool
    is_favorite: bool = False
    is_open_now: bool = False
    can_order_now: bool = False
    order_block_reason: str | None = None
    distance_km: float | None = None

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_active: bool | None = None
    working_hours: list[OrganizationWorkingHourUpdate] | None = None

    @field_validator("name", "address", "city", "phone")
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        return value or None


class OrganizationCreate(OrganizationUpdate):
    name: str


class UserRead(BaseModel):
    id: int
    organization_id: int | None = None
    email: str | None = None
    username: str | None = None
    oib: str | None = None
    role: UserRole
    student_card_number: str | None = None
    student_esi: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    profile_image_url: str | None = None
    subsidy_remaining: float | None = None
    is_active: bool
    organization: OrganizationRead | None = None
    organizations: list[OrganizationRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        return value or None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Nova lozinka mora imati najmanje 6 znakova")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminCreate(BaseModel):
    """Schema for creating a new admin/staff user.

    Staff users authenticate using username + password (not email).
    Required fields: first_name, last_name, username (unique), oib (unique), password.
    """

    username: str = Field(min_length=3, max_length=50)
    password: str
    oib: str = Field(min_length=11, max_length=11)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    organization_ids: list[int] | None = None

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        value = v.strip()
        if not value.isalnum():
            raise ValueError("Korisničko ime smije sadržavati samo slova i brojeve")
        return value

    @field_validator("oib")
    @classmethod
    def oib_numeric(cls, v: str) -> str:
        value = v.strip()
        if not value.isdigit():
            raise ValueError("OIB mora sadržavati samo brojeve")
        return value

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Lozinka mora imati najmanje 6 znakova")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_names(cls, v: str) -> str:
        return v.strip()


class AdminUpdate(BaseModel):
    is_active: bool | None = None


class AdminOrganizationsUpdate(BaseModel):
    organization_ids: list[int]


class AdminMoveOrganizationRequest(BaseModel):
    from_organization_id: int
    to_organization_id: int


class StudentCardInfo(BaseModel):
    card_number: str
    esi: str
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    faculty: str | None = None
    profile_image_url: str | None = None
    subsidy_remaining: float | None = None
    source: str = "issp"


class ISSPLinkRequest(BaseModel):
    method: str = "manual"  # manual | qr
    card_number: str | None = None
    esi: str | None = None
    qr_payload: str | None = None

    @model_validator(mode="after")
    def validate_method_payload(self):
        method = (self.method or "manual").strip().lower()
        if method not in {"manual", "qr"}:
            raise ValueError("method mora biti 'manual' ili 'qr'")
        self.method = method
        if method == "manual":
            if not self.card_number or not self.esi:
                raise ValueError("Za manual mode card_number i esi su obavezni")
            self.card_number = validate_student_card_number(self.card_number)
            self.esi = self.esi.strip()
            if not self.esi:
                raise ValueError("ESI broj je obavezan")
            return self
        if not self.qr_payload or not self.qr_payload.strip():
            raise ValueError("Za qr mode qr_payload je obavezan")
        self.qr_payload = self.qr_payload.strip()
        return self


class ISSPServiceUnavailable(BaseModel):
    """Response schema for when ISSP service is not configured or unavailable.

    This provides a structured, user-friendly error response instead of
    exposing internal configuration details or stack traces.
    """

    error: str = "ISSP_NOT_CONFIGURED"
    message: str = (
        "ISSP integracija nije konfigurirana na backendu. "
        "Povezivanje je spremno i aktivira se nakon unosa ISSP pristupnih podataka."
    )


# ---------------------------------------------------------------------------
# Menu schemas
# ---------------------------------------------------------------------------


class MenuItemCreate(BaseModel):
    code: int
    name: str
    description: str | None = None
    image_url: str | None = None
    price: float
    category: str = "Ostalo"
    group_code: int
    unit: str = "KOM"
    is_available: bool = True
    calories_kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    organization_id: int | None = None

    @field_validator("code", "group_code")
    @classmethod
    def positive_int(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Vrijednost mora biti pozitivna")
        return v

    @field_validator("unit")
    @classmethod
    def unit_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("JM ne moze biti prazna")
        return v.strip()

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Cijena mora biti 0 ili veca")
        return v

    @field_validator("calories_kcal", "protein_g", "carbs_g", "fat_g")
    @classmethod
    def nutrition_non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Nutritivna vrijednost mora biti 0 ili veca")
        return v

    @field_validator("image_url")
    @classmethod
    def normalize_image_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip()
        return normalized or None


class MenuItemUpdate(BaseModel):
    code: int | None = None
    name: str | None = None
    description: str | None = None
    image_url: str | None = None
    price: float | None = None
    category: str | None = None
    group_code: int | None = None
    unit: str | None = None
    is_available: bool | None = None
    calories_kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    organization_id: int | None = None

    @field_validator("code", "group_code")
    @classmethod
    def positive_int_optional(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("Vrijednost mora biti pozitivna")
        return v

    @field_validator("unit")
    @classmethod
    def unit_not_empty_optional(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("JM ne moze biti prazna")
        return v.strip() if v is not None else v

    @field_validator("price")
    @classmethod
    def price_non_negative_optional(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Cijena mora biti 0 ili veca")
        return v

    @field_validator("calories_kcal", "protein_g", "carbs_g", "fat_g")
    @classmethod
    def nutrition_non_negative_optional(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Nutritivna vrijednost mora biti 0 ili veca")
        return v

    @field_validator("image_url")
    @classmethod
    def normalize_image_url_optional(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip()
        return normalized or None


class MenuItemRead(BaseModel):
    id: int
    organization_id: int | None
    organization_name: str | None = None
    code: int
    name: str
    description: str | None
    image_url: str | None
    price: float
    category: str
    group_code: int
    unit: str
    is_available: bool
    is_orderable: bool = True
    calories_kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Order schemas
# ---------------------------------------------------------------------------


class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Kolicina mora biti najmanje 1")
        return v


class OrderItemRead(BaseModel):
    id: int
    menu_item_id: int
    quantity: int
    price_at_order: float
    menu_item_name: str | None = None

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    pickup_time: datetime
    notes: str | None = None
    items: list[OrderItemCreate]
    organization_id: int | None = None


class OrderUpdate(BaseModel):
    pickup_time: datetime | None = None
    notes: str | None = None
    items: list[OrderItemCreate] | None = None


class OrderRead(BaseModel):
    id: int
    user_id: int
    organization_id: int | None = None
    pickup_time: datetime
    status: OrderStatus
    created_at: datetime
    notes: str | None
    items: list[OrderItemRead]
    total_price: float

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class PopularMenuItemStat(BaseModel):
    menu_item_id: int
    menu_item_name: str | None = None
    order_count: int


# ---------------------------------------------------------------------------
# Rating schemas
# ---------------------------------------------------------------------------


class MealRatingCreate(BaseModel):
    menu_item_id: int
    rating: int = Field(ge=1, le=5)


class MealRatingRead(BaseModel):
    id: int
    user_id: int
    menu_item_id: int
    rating: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MealRatingSummaryRead(BaseModel):
    menu_item_id: int
    average_rating: float
    rating_count: int
