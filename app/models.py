from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


class UserRole(StrEnum):
    student = "student"
    admin = "admin"
    owner = "owner"


# ---------------------------------------------------------------------------
# Link tables
# ---------------------------------------------------------------------------


class UserOrganization(SQLModel, table=True):
    __tablename__ = "user_organizations"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class UserFavoriteOrganization(SQLModel, table=True):
    __tablename__ = "user_favorite_organizations"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Organization + User
# ---------------------------------------------------------------------------


class Organization(SQLModel, table=True):
    __tablename__ = "organizations"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, index=True, max_length=100)
    phone: str | None = Field(default=None, max_length=40)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    users: list["User"] = Relationship(back_populates="organization")
    members: list["User"] = Relationship(
        back_populates="organizations",
        link_model=UserOrganization,
    )
    working_hours: list["OrganizationWorkingHour"] = Relationship(
        back_populates="organization"
    )
    favorited_by: list["User"] = Relationship(
        back_populates="favorite_organizations",
        link_model=UserFavoriteOrganization,
    )
    menu_items: list["MenuItem"] = Relationship(back_populates="organization")
    orders: list["Order"] = Relationship(back_populates="organization")


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int | None = Field(
        default=None, foreign_key="organizations.id", index=True
    )
    email: str | None = Field(default=None, index=True)  # Optional for staff users
    username: str | None = Field(
        default=None, unique=True, index=True, max_length=50
    )  # Unique username for staff
    oib: str | None = Field(
        default=None, unique=True, index=True, max_length=11
    )  # OIB for staff users
    hashed_password: str
    role: UserRole = Field(default=UserRole.student)
    student_card_number: str | None = Field(
        default=None, index=True, unique=True, max_length=32
    )
    student_esi: str | None = Field(
        default=None, index=True, unique=True, max_length=32
    )
    first_name: str | None = Field(default=None, max_length=50)
    last_name: str | None = Field(default=None, max_length=50)
    profile_image_url: str | None = Field(default=None, max_length=512)
    subsidy_remaining: float | None = Field(default=None, ge=0)
    is_active: bool = Field(default=True)

    organization: Organization | None = Relationship(back_populates="users")
    organizations: list[Organization] = Relationship(
        back_populates="members",
        link_model=UserOrganization,
    )
    favorite_organizations: list[Organization] = Relationship(
        back_populates="favorited_by",
        link_model=UserFavoriteOrganization,
    )
    orders: list["Order"] = Relationship(back_populates="user")
    meal_ratings: list["MealRating"] = Relationship(back_populates="user")


# ---------------------------------------------------------------------------
# Organization working hours
# ---------------------------------------------------------------------------


class OrganizationWorkingHour(SQLModel, table=True):
    __tablename__ = "organization_working_hours"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "day_of_week",
            name="uq_org_working_hours_org_day",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", index=True)
    day_of_week: int = Field(ge=0, le=6, index=True)
    is_closed: bool = Field(default=False)
    open_time: str | None = Field(default=None, max_length=5)
    close_time: str | None = Field(default=None, max_length=5)

    organization: Organization | None = Relationship(back_populates="working_hours")


# ---------------------------------------------------------------------------
# MenuItem
# ---------------------------------------------------------------------------


class MenuItem(SQLModel, table=True):
    __tablename__ = "menu_items"

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int | None = Field(
        default=None, foreign_key="organizations.id", index=True
    )
    code: int = Field(index=True, ge=1)
    name: str = Field(index=True, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=512)
    price: float = Field(ge=0)
    category: str = Field(default="Ostalo", max_length=50)
    group_code: int = Field(index=True, ge=1)
    unit: str = Field(default="KOM", max_length=10)
    is_available: bool = Field(default=True)

    calories_kcal: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)

    organization: Organization | None = Relationship(back_populates="menu_items")
    order_items: list["OrderItem"] = Relationship(back_populates="menu_item")
    meal_ratings: list["MealRating"] = Relationship(back_populates="menu_item")


# ---------------------------------------------------------------------------
# Order + OrderItem
# ---------------------------------------------------------------------------


class OrderStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    ready = "ready"
    completed = "completed"
    cancelled = "cancelled"


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    menu_item_id: int = Field(foreign_key="menu_items.id", index=True)
    quantity: int = Field(default=1, ge=1)
    price_at_order: float

    order: Optional["Order"] = Relationship(back_populates="items")
    menu_item: Optional["MenuItem"] = Relationship(back_populates="order_items")


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int | None = Field(
        default=None, foreign_key="organizations.id", index=True
    )
    user_id: int = Field(foreign_key="users.id", index=True)
    pickup_time: datetime
    status: OrderStatus = Field(default=OrderStatus.pending)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    notes: str | None = Field(default=None, max_length=300)

    organization: Organization | None = Relationship(back_populates="orders")
    user: User | None = Relationship(back_populates="orders")
    items: list["OrderItem"] = Relationship(back_populates="order")


# ---------------------------------------------------------------------------
# Meal ratings
# ---------------------------------------------------------------------------


class MealRating(SQLModel, table=True):
    __tablename__ = "meal_ratings"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "menu_item_id",
            name="uq_meal_ratings_user_menu_item",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    menu_item_id: int = Field(foreign_key="menu_items.id", index=True)
    rating: int = Field(ge=1, le=5)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    user: User | None = Relationship(back_populates="meal_ratings")
    menu_item: MenuItem | None = Relationship(back_populates="meal_ratings")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class LoginAudit(SQLModel, table=True):
    __tablename__ = "login_audits"

    id: int | None = Field(default=None, primary_key=True)
    student_card_number: str = Field(index=True, max_length=32)
    user_id: int | None = Field(default=None, foreign_key="users.id")
    success: bool
    ip_address: str | None = Field(default=None, max_length=45)
    reason: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
