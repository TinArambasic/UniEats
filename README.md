# UniEats Menza Pre-Order

REST API sustav za narucivanje obroka u menzi unaprijed. Fokus je na procesu (planiranje, testiranje, CI, Docker, dokumentacija) i jasnim osnovnim tokovima.

## Stack

| Komponenta | Tehnologija |
| --- | --- |
| Web framework | FastAPI + Uvicorn |
| Validacija | Pydantic v2 |
| Baza | SQLite |
| ORM | SQLModel |
| Autentifikacija | JWT (python-jose + passlib) |
| Testiranje | pytest + httpx |
| Lint / format | ruff + black |
| Migracije | Alembic |
| CI | GitHub Actions |
| Kontejnerizacija | Docker + Docker Compose |

## Struktura projekta

```
menza-preorder/
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- database.py
|   |-- auth.py
|   |-- dependencies.py
|   |-- logging.py
|   |-- models.py
|   |-- schemas.py
|   |-- validators.py
|   |-- routers/
|       |-- auth.py
|       |-- menu.py
|       |-- orders.py
|       |-- students.py
|   |-- services/
|       |-- auth_service.py
|       |-- issp_service.py
|       |-- menu_service.py
|       |-- order_service.py
|       |-- rate_limiter.py
|-- alembic/
|   |-- env.py
|   |-- versions/
|-- tests/
|-- docs/
|   |-- backlog.md
|-- .github/workflows/ci.yml
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- requirements-dev.txt
|-- pyproject.toml
```

## Pokretanje lokalno

Preduvjeti:
- Python 3.11+

Instalacija:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt
```

Konfiguracija:

```bash
# Kopiraj primjer
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux
```

Za produkciju koristi `.env.production.example` kao bazu.

Pokretanje:

```bash
# Primijeni migracije (obavezno)
alembic upgrade head

# Pokreni API
uvicorn app.main:app --reload
```

API je dostupan na `http://localhost:8000`.
Swagger UI: `http://localhost:8000/docs`.

Dodatne sigurnosne postavke (env):
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `LOGIN_RATE_LIMIT_MAX`
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `RATE_LIMITER_BACKEND` (`memory` ili `redis`)
- `REDIS_URL` (ako se koristi Redis)
- `LOG_FILE_PATH`, `LOG_ROTATION`, `LOG_FILE_MAX_BYTES`, `LOG_FILE_BACKUP_COUNT`
- `OWNER_EMAIL`, `OWNER_PASSWORD` (opcionalni bootstrap owner korisnika)
- `OWNER_FIRST_NAME`, `OWNER_LAST_NAME`
- `MENU_IMAGE_UPLOAD_DIR`, `MENU_IMAGE_MAX_BYTES`
- `MENU_IMAGE_MAX_WIDTH`, `MENU_IMAGE_MAX_HEIGHT`

## Kreiranje OWNER korisnika

Sustav podrzava 2 nacina:

1. Automatski bootstrap pri pokretanju aplikacije (env):
   - postavi `OWNER_EMAIL` i `OWNER_PASSWORD` u `.env`
   - opcionalno postavi `OWNER_FIRST_NAME` i `OWNER_LAST_NAME`
   - pokreni aplikaciju; owner se kreira ako ne postoji korisnik s tim emailom

2. CLI skripta:
```bash
py scripts/create_owner.py --email owner@example.com --password JakaLozinka123!
```

Napomene:
- Ako owner ne postoji, aplikacija ce zapisati upozorenje u log.
- Zadnjeg OWNER korisnika nije moguce obrisati (`DELETE /auth/owners/{id}` vraca 400).
- `scripts/create_owner.py` ne mijenja shemu baze; zahtijeva da su migracije
  unaprijed primijenjene (`alembic upgrade head`).

## Baza i migracije (Alembic)

Schema se upravlja iskljucivo putem Alembic migracija:

```bash
# Primijeni zadnju migraciju
alembic upgrade head

# Kreiraj novu migraciju nakon promjene modela
alembic revision --autogenerate -m "opis_promjene"
```

Napomena:
- Migracija `0007_make_student_fields_nullable` osigurava da su
  `users.student_card_number` i `users.student_esi` nullable, kako bi
  OWNER/ADMIN korisnici mogli postojati bez studentskih podataka.
- Aplikacija i owner CLI rade read-only provjeru revizije baze; ako baza nije
  na head reviziji, ispisuje se uputa za `alembic upgrade head`.

## Testiranje i lint

```bash
pytest
ruff check .
black --check .
```

## Docker

```bash
docker compose up --build
```

Pokrece se API i Redis (za rate limiting). Baza je u `./data/menza.db`.

## Deploy (VPS)

Detaljan vodič je u `docs/deploy.md`.

## Production konfiguracija (preporuka)

- Kopiraj `.env.production.example` u `.env`
- Postavi jaki `SECRET_KEY`
- Postavi `ENVIRONMENT=production`
- Postavi `RATE_LIMITER_BACKEND=redis` i ispravan `REDIS_URL`
- Pokreni migracije prije aplikacije:

```bash
alembic upgrade head
```

## API - kratki pregled

Svi endpointi (osim `/auth/*` i `/health`) zahtijevaju Bearer token.

Auth:
- `POST /auth/register` - Registracija novog studenta
- `POST /auth/login/student` - Prijava studenta (broj kartice + lozinka)
- `POST /auth/login/staff` - Prijava djelatnika (korisničko ime + lozinka)
- `POST /auth/login` (legacy alias na student login)
- `GET /auth/me` - Dohvat vlastitog profila
Napomena: OAuth2 password flow koristi polje `username` u formi.
Student login: `username=broj_kartice`.
Admin/Owner login: `username=korisničko_ime` (nije email!).
Broj kartice mora biti numerički (6-32 znamenke) i koristi se samo za studente.
Login endpoint ima rate limit, a pokušaji prijave se auditiraju (tablica `login_audits`).

Owner -> admin management:
- `POST /auth/admins` (owner kreira djelatnika s username, oib, lozinkom)
- `GET /auth/admins` (owner pregled djelatnika)
- `PATCH /auth/admins/{id}` (owner aktivira/deaktivira djelatnika)
- `DELETE /auth/admins/{id}` (owner briše djelatnika)

Owner -> owner management:
- `GET /auth/owners` (owner pregled owner korisnika)
- `DELETE /auth/owners/{id}` (owner brisanje owner korisnika; zadnjeg nije moguce obrisati)

Student card:
- `GET /students/status` (status ISSP integracije)
- `GET /students/card-info` (auth, dohvat podataka s studentske iskaznice putem ISSP SRCE API-ja)
- `POST /students/card-lookup?card_number=...&esi=...` (auth, proizvoljan dohvat podataka s iskaznice)
- `POST /students/issp/link` (auth student, povezivanje ISSP računa preko ESI+kartica ili QR payloada)
- `POST /students/issp/sync` (auth student, osvježavanje ISSP podataka za već povezani račun)

Jelovnik:
- `GET /menu/items` (auth, samo dostupni)
- `GET /menu/items?available_only=false` (auth, puni jelovnik ukljucujuci i nedostupne artikle)
- `GET /menu/items/{id}` (auth)
- `POST /menu/items` (admin/owner)
- `PUT /menu/items/{id}` (admin/owner)
- `DELETE /menu/items/{id}` (admin/owner)
- `POST /menu/items/{id}/image` (admin/owner upload slike)
- `DELETE /menu/items/{id}/image` (admin/owner uklanjanje slike)

Narudzbe:
- `POST /orders/` (auth)
- `PATCH /orders/{id}` (auth, pending only)
- `DELETE /orders/{id}/items` (auth, praznjenje kosarice)
- `GET /orders/my` (auth)
- `GET /orders/popular` (auth, popularnost jela prema stvarnim narudzbama)
- `GET /orders/all` (admin/owner)
- `GET /orders/{id}` (auth ili admin/owner)
- `PATCH /orders/{id}/status` (admin/owner)
- `DELETE /orders/{id}` (auth ili admin/owner)

Health:
- `GET /health`

## ISSP SRCE (integracija)

Sustav podržava integraciju s ISSP SRCE API-jem za dohvat podataka sa studentskih iskaznica.

Konfiguracija:
```bash
# U .env datoteku dodati:
ISSP_CLIENT_ID=vaz_klijent_id
ISSP_CLIENT_SECRET=vaz_klijent_secret
ISSP_API_BASE_URL=https://isspapi.issp.srce.hr/api  # opcionalno
```

API dokumentacija: https://isspapi.issp.srce.hr/index.html
Referentna implementacija: https://github.com/mzo-srce/restoran-klijent (MIT licenca)

Kada je konfiguriran, endpoint `GET /students/card-info` će dohvatiti stvarne podatke
s ISSP SRCE API-ja. U suprotnom vraća strukturirani HTTP 503 odgovor.

Podržani ISSP flowovi u aplikaciji:
- ručni unos (`ESI + broj kartice`) preko `POST /students/issp/link`
- QR payload povezivanje preko `POST /students/issp/link` (`method=qr`)
- osvježavanje povezanih podataka preko `POST /students/issp/sync`

## Logging i PII politika

- Ne logiramo lozinke, tokene ili druge tajne.
- Broj kartice se u logovima maskira (zvjezdice + zadnje 4 znamenke).
- Puni broj kartice se cuva iskljucivo u audit tablici `login_audits` zbog sigurnosti.
- Rotacija logova je podesiva (velicina ili vrijeme) kroz `LOG_ROTATION` i pripadne varijable.

## Poslovna pravila

- Nedostupni artikli se ne mogu naruciti.
- Upload slike je dozvoljen samo `admin/owner` korisnicima.
- Slike se spremaju u `static/uploads/menu`.
- Dozvoljeni formati slika: `image/jpeg`, `image/png`, `image/webp`.
- MIME tip se provjerava server-side na osnovi magic bytes.
- Slike prolaze sanitizaciju (ponovno enkodiranje) prije spremanja.
- Maksimalna velicina datoteke i dimenzije slike su ogranicene preko:
  - `MENU_IMAGE_MAX_BYTES`
  - `MENU_IMAGE_MAX_WIDTH`
  - `MENU_IMAGE_MAX_HEIGHT`
- Pickup time mora biti u buducnosti.
- Ako su `ORDER_WINDOW_START_HOUR` i `ORDER_WINDOW_END_HOUR` postavljeni, pickup time mora biti unutar tog prozora.
- Otkazivanje je dozvoljeno samo za `pending` i `confirmed`.
- Uredivanje narudzbe je dozvoljeno samo za `pending`.
- Praznjenje kosarice postavlja narudzbu na `cancelled`.

## Osnovni tok (kratko)

1. `POST /auth/login/staff` (admin)
2. `POST /menu/items` (admin doda artikal)
3. `POST /auth/register` (student)
4. `POST /auth/login/student` (student)
5. `GET /menu/items` (student vidi jelovnik)
6. `POST /orders/` (student naruci)
7. `GET /orders/my` (student vidi status)
8. `PATCH /orders/{id}/status` (admin potvrdi i oznaci ready)
9. (Opcionalno) `GET /students/card-info` kada sluzbeni API postane dostupan

## Backlog

Backlog i razrada taskova je u `docs/backlog.md`.
