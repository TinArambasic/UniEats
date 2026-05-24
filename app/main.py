from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.config import settings
from app.database import engine
from app.logging import log_event
from app.routers import auth, menu, orders, organizations, ratings, students
from app.schema_guard import SchemaOutOfDateError, require_schema_at_head
from app.services.auth_service import ensure_owner_presence, seed_owner_if_configured


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate DB schema, initialize services, and run startup seeding."""
    schema_ready = True
    try:
        state = require_schema_at_head(engine)
        log_event(
            "db_schema_check_ok",
            current_heads=sorted(state.current_heads),
            expected_heads=sorted(state.expected_heads),
        )
    except SchemaOutOfDateError as exc:
        schema_ready = False
        log_event("db_schema_check_failed", reason=str(exc))
        if settings.ENVIRONMENT == "production":
            raise

    if schema_ready:
        with Session(engine) as session:
            try:
                seed_owner_if_configured(session)
            except Exception as exc:
                log_event("owner_seed_error", reason=str(exc))
            if not ensure_owner_presence(session):
                log_event(
                    "owner_missing_warning",
                    message=(
                        "Nije pronaden OWNER korisnik. Kreirajte ga preko "
                        "OWNER_EMAIL/OWNER_PASSWORD ili scripts/create_owner.py"
                    ),
                )
    else:
        log_event(
            "owner_seed_skipped",
            reason="Schema nije na latest reviziji. Pokrenite alembic upgrade head.",
        )
    yield


app = FastAPI(
    title="UniEats Menza Pre-Order API",
    description=(
        "API za narucivanje obroka u menzi unaprijed.\n\n"
        "Uloge:\n"
        "- student: pregled jelovnika, kreiranje narudzbi (kartica + ESI)\n"
        "- admin (djelatnik): CRUD artikala, pregled narudzbi svoje organizacije\n"
        "- owner (admin organizacije): sve staff ovlasti + upravljanje djelatnicima"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(ratings.router)
app.include_router(students.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "menza-preorder", "version": "1.0.0"}


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse("static/index.html", media_type="text/html; charset=utf-8")
