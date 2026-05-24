from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.auth import create_access_token
from app.database import get_session
from app.dependencies import get_current_user, require_admin, require_owner
from app.schemas import (
    AdminCreate,
    AdminMoveOrganizationRequest,
    AdminOrganizationsUpdate,
    AdminUpdate,
    Token,
    UserCreate,
    UserPasswordUpdate,
    UserProfileUpdate,
    UserRead,
)
from app.services.auth_service import (
    add_admin_organization,
    authenticate_staff_user,
    authenticate_student_user,
    clear_profile_image,
    create_admin_user,
    delete_admin_user,
    delete_owner_user,
    list_admin_users,
    list_organization_users,
    list_owner_users,
    move_admin_organization,
    register_user,
    remove_admin_organization,
    set_admin_organizations,
    set_profile_image,
    update_admin_status,
    update_password,
    update_profile,
)
from app.services.image_service import delete_profile_image_file, save_profile_image

router = APIRouter(prefix="/auth", tags=["Autentifikacija"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=201,
    summary="Registracija novog studenta",
)
def register(user_data: UserCreate, session: Session = Depends(get_session)):
    return register_user(session, user_data)


@router.post(
    "/login/student",
    response_model=Token,
    summary="Prijava studenta - broj studentske iskaznice + lozinka",
)
def login_student(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    card_number = form_data.username.strip()
    ip_address = request.client.host if request.client else None
    user = authenticate_student_user(
        session=session,
        card_number=card_number,
        password=form_data.password,
        ip_address=ip_address,
    )
    token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=token)


@router.post(
    "/login/staff",
    response_model=Token,
    summary="Prijava admin/owner korisnika - korisničko ime + lozinka",
)
def login_staff(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Staff login using username (not email).

    Staff users (admin/owner) authenticate with their unique username and password.
    The username is passed in the 'username' field of OAuth2PasswordRequestForm.
    """
    username = form_data.username.strip()
    ip_address = request.client.host if request.client else None
    user = authenticate_staff_user(
        session=session,
        username=username,
        password=form_data.password,
        ip_address=ip_address,
    )
    token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=token)


@router.post(
    "/login",
    response_model=Token,
    summary="Legacy login (student route)",
)
def login_legacy_student(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    return login_student(request=request, form_data=form_data, session=session)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Informacije o trenutno prijavljenom korisniku",
)
def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Azuriraj vlastiti profil",
)
def patch_me(
    update_data: UserProfileUpdate,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    return update_profile(session, current_user, update_data)


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Promijeni vlastitu lozinku",
)
def patch_my_password(
    payload: UserPasswordUpdate,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    update_password(
        session=session,
        current_user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )


@router.post(
    "/me/avatar",
    response_model=UserRead,
    summary="Upload profilne slike",
)
async def upload_my_avatar(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    old_url = current_user.profile_image_url
    image_url = await save_profile_image(file)
    try:
        user = set_profile_image(session, current_user, image_url)
    except Exception:
        delete_profile_image_file(image_url)
        raise
    if old_url != image_url:
        delete_profile_image_file(old_url)
    return user


@router.delete(
    "/me/avatar",
    response_model=UserRead,
    summary="Ukloni profilnu sliku",
)
def delete_my_avatar(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    old_url = current_user.profile_image_url
    user = clear_profile_image(session, current_user)
    delete_profile_image_file(old_url)
    return user


@router.post(
    "/admins",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Owner kreira djelatnika",
)
def create_admin(
    admin_data: AdminCreate,
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    return create_admin_user(session, owner_user, admin_data)


@router.get(
    "/admins",
    response_model=list[UserRead],
    summary="Owner pregled djelatnika",
)
def get_admins(
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    return list_admin_users(session, owner_user)


@router.patch(
    "/admins/{admin_id}",
    response_model=UserRead,
    summary="Owner aktivira/deaktivira djelatnika",
)
def patch_admin(
    admin_id: int,
    update_data: AdminUpdate,
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    if update_data.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Potrebno je poslati polje is_active",
        )
    return update_admin_status(session, owner_user, admin_id, update_data.is_active)


@router.put(
    "/admins/{admin_id}/organizations",
    response_model=UserRead,
    summary="Postavi organizacije djelatnika",
)
def put_admin_organizations(
    admin_id: int,
    payload: AdminOrganizationsUpdate,
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    return set_admin_organizations(
        session, owner_user, admin_id, payload.organization_ids
    )


@router.post(
    "/admins/{admin_id}/organizations/{organization_id}",
    response_model=UserRead,
    summary="Dodaj djelatnika u organizaciju",
)
def post_admin_organization(
    admin_id: int,
    organization_id: int,
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    return add_admin_organization(session, owner_user, admin_id, organization_id)


@router.delete(
    "/admins/{admin_id}/organizations/{organization_id}",
    response_model=UserRead,
    summary="Ukloni djelatnika iz organizacije",
)
def delete_admin_organization(
    admin_id: int,
    organization_id: int,
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    return remove_admin_organization(session, owner_user, admin_id, organization_id)


@router.post(
    "/admins/{admin_id}/move-organization",
    response_model=UserRead,
    summary="Premjesti djelatnika izmedu organizacija",
)
def post_move_admin_organization(
    admin_id: int,
    payload: AdminMoveOrganizationRequest,
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    return move_admin_organization(
        session,
        owner_user,
        admin_id,
        payload.from_organization_id,
        payload.to_organization_id,
    )


@router.delete(
    "/admins/{admin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Owner brise djelatnika",
)
def remove_admin(
    admin_id: int,
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    delete_admin_user(session, owner_user, admin_id)


@router.get(
    "/users",
    response_model=list[UserRead],
    summary="Korisnici unutar organizacije",
)
def get_organization_users(
    organization_id: int | None = None,
    session: Session = Depends(get_session),
    current_user=Depends(require_admin),
):
    return list_organization_users(
        session, current_user, organization_id=organization_id
    )


@router.get(
    "/owners",
    response_model=list[UserRead],
    summary="Pregled owner korisnika",
)
def get_owners(
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    return list_owner_users(session, owner_user)


@router.delete(
    "/owners/{owner_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Brisanje owner korisnika (ne moze zadnjeg)",
)
def remove_owner(
    owner_id: int,
    session: Session = Depends(get_session),
    owner_user=Depends(require_owner),
):
    delete_owner_user(session, owner_user, owner_id)
