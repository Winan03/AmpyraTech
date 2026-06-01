from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Any, Callable, Mapping, Optional
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import db as firebase_db
import os
import re

if os.getenv("VERCEL") != "1":
    load_dotenv(override=os.getenv("SKIP_FIREBASE_INIT", "false").lower() not in {"1", "true", "yes"})

# --- Configuración de Seguridad ---
def _get_required_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    joined_names = " o ".join(names)
    raise RuntimeError(f"{joined_names} no está configurada en el entorno.")


def _get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} debe ser un número entero.") from exc


SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or ""
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = _get_int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
SKIP_FIREBASE_INIT = os.getenv("SKIP_FIREBASE_INIT", "false").lower() in {"1", "true", "yes"}
AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "local").strip().lower()
ALLOW_LEGACY_PASSWORD_LOGIN = os.getenv(
    "ALLOW_LEGACY_PASSWORD_LOGIN",
    "true" if SKIP_FIREBASE_INIT or AUTH_PROVIDER == "local" else "false",
).lower() in {"1", "true", "yes"}
CHECK_FIREBASE_TOKEN_REVOKED = os.getenv("CHECK_FIREBASE_TOKEN_REVOKED", "true").lower() in {"1", "true", "yes"}
DISABLE_FIREBASE_AUTH_USER_MANAGEMENT = os.getenv(
    "DISABLE_FIREBASE_AUTH_USER_MANAGEMENT",
    "false",
).lower() in {"1", "true", "yes"}
if ALLOW_LEGACY_PASSWORD_LOGIN and not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY o SECRET_KEY debe estar configurada para login local legacy.")
VALID_ROLES = {"admin", "operativo", "auditor"}
ACTIVE_STATUS = "activo"
VALID_ACCOUNT_STATUSES = {ACTIVE_STATUS, "deshabilitado", "congelado"}
USER_STORE_PATH = os.getenv("USER_STORE_PATH", "/app_users")
FIREBASE_USER_STORE_DISABLED = os.getenv("DISABLE_FIREBASE_USER_STORE", "false").lower() in {"1", "true", "yes"}
TERMS_VERSION = os.getenv("TERMS_VERSION", "2026-05-31")
TERMS_CONSENT_STORE_PATH = os.getenv("TERMS_CONSENT_STORE_PATH", "/app_consents")
TERMS_REQUIRED_ROLES_RAW = os.getenv("TERMS_REQUIRED_ROLES", "admin,operativo,auditor")

# Contexto para Hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema de OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter()

# --- Modelos ---
class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class User(BaseModel):
    uid: Optional[str] = None
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    status: str = ACTIVE_STATUS
    disabled: Optional[bool] = None
    auth_provider: str = "local"

class UserInDB(User):
    hashed_password: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=12)
    role: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    status: str = ACTIVE_STATUS


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=12)


class AuthConfig(BaseModel):
    provider: str
    firebase_web_config: Optional[dict[str, str]] = None
    legacy_password_login_enabled: bool


class FirebaseSession(BaseModel):
    token_type: str
    user: User


class ConsentStatus(BaseModel):
    requires_acceptance: bool
    accepted: bool
    terms_version: str
    accepted_version: Optional[str] = None
    accepted_at: Optional[str] = None


class ConsentAcceptRequest(BaseModel):
    terms_version: Optional[str] = None


class ConsentRecord(BaseModel):
    username: str
    uid: Optional[str] = None
    role: str
    terms_version: str
    accepted_at: str
    event_type: str = "terms_acceptance"


fake_consent_db: dict[str, list[dict[str, Any]]] = {}

def _validate_role(role: str) -> str:
    normalized_role = role.strip().lower()
    if normalized_role not in VALID_ROLES:
        raise RuntimeError(f"Rol inválido: {role}. Roles válidos: {', '.join(sorted(VALID_ROLES))}.")
    return normalized_role


def _validate_account_status(account_status: str) -> str:
    normalized_status = account_status.strip().lower()
    if normalized_status not in VALID_ACCOUNT_STATUSES:
        raise RuntimeError(
            f"Estado de cuenta inválido: {account_status}. "
            f"Estados válidos: {', '.join(sorted(VALID_ACCOUNT_STATUSES))}."
        )
    return normalized_status


def _parse_terms_required_roles() -> set[str]:
    roles = {role.strip().lower() for role in TERMS_REQUIRED_ROLES_RAW.split(",") if role.strip()}
    if not roles:
        return set()
    invalid_roles = roles - VALID_ROLES
    if invalid_roles:
        raise RuntimeError(
            f"TERMS_REQUIRED_ROLES contiene roles invalidos: {', '.join(sorted(invalid_roles))}."
        )
    return roles


TERMS_REQUIRED_ROLES = _parse_terms_required_roles()


def _build_users_db() -> dict[str, dict[str, Any]]:
    username = _get_required_env("ADMIN_USERNAME")
    password_hash = os.getenv("ADMIN_PASSWORD_HASH")
    password_plain = os.getenv("ADMIN_PASSWORD")
    admin_firebase_uid = os.getenv("ADMIN_FIREBASE_UID")
    admin_status = _validate_account_status(os.getenv("ADMIN_STATUS", ACTIVE_STATUS))
    admin_disabled = os.getenv("ADMIN_DISABLED", "false").lower() == "true"

    if ALLOW_LEGACY_PASSWORD_LOGIN and not password_hash and not password_plain:
        raise RuntimeError("ADMIN_PASSWORD_HASH o ADMIN_PASSWORD debe estar configurada en el entorno.")

    return {
        username: {
            "uid": admin_firebase_uid or "",
            "username": username,
            "full_name": os.getenv("ADMIN_FULL_NAME", "Admin Safyra"),
            "email": os.getenv("ADMIN_EMAIL", ""),
            "role": _validate_role(os.getenv("ADMIN_ROLE", "admin")),
            "status": "deshabilitado" if admin_disabled else admin_status,
            "hashed_password": password_hash or (pwd_context.hash(password_plain) if password_plain else ""),
            "disabled": admin_disabled,
            "auth_provider": "firebase" if admin_firebase_uid else "local",
        }
    }


fake_users_db = _build_users_db()

# --- Funciones de Utilidad ---
def _public_user_from_record(user_record: Mapping[str, Any]) -> User:
    return User(
        uid=user_record.get("uid"),
        username=str(user_record["username"]),
        email=user_record.get("email"),
        full_name=user_record.get("full_name"),
        role=str(user_record["role"]),
        status=str(user_record.get("status", ACTIVE_STATUS)),
        disabled=bool(user_record.get("disabled", False)),
        auth_provider=str(user_record.get("auth_provider", "local")),
    )


def _public_user_from_model(user: UserInDB) -> User:
    if hasattr(user, "model_dump"):
        user_data = user.model_dump(exclude={"hashed_password"})
    else:
        user_data = user.dict(exclude={"hashed_password"})
    return User(**user_data)


def _normalize_username(username: str) -> str:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El username no puede estar vacío")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized_username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El username solo puede contener letras, números, guion y guion bajo",
        )
    invalid_key_chars = {".", "#", "$", "[", "]", "/"}
    if any(char in normalized_username for char in invalid_key_chars):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El username contiene caracteres no permitidos",
        )
    return normalized_username


def _parse_role_for_request(role: str) -> str:
    try:
        return _validate_role(role)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _parse_status_for_request(account_status: str) -> str:
    try:
        return _validate_account_status(account_status)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def _firebase_user_store_enabled() -> bool:
    return not FIREBASE_USER_STORE_DISABLED and not SKIP_FIREBASE_INIT and bool(firebase_admin._apps)


def _firebase_auth_enabled() -> bool:
    return AUTH_PROVIDER == "firebase" and not SKIP_FIREBASE_INIT and bool(firebase_admin._apps)


def _firebase_auth_user_management_enabled() -> bool:
    return _firebase_auth_enabled() and not DISABLE_FIREBASE_AUTH_USER_MANAGEMENT


def _firebase_consent_store_enabled() -> bool:
    return not SKIP_FIREBASE_INIT and bool(firebase_admin._apps)


def _get_firebase_web_config() -> Optional[dict[str, str]]:
    config_fields = {
        "apiKey": "FIREBASE_WEB_API_KEY",
        "authDomain": "FIREBASE_AUTH_DOMAIN",
        "projectId": "FIREBASE_PROJECT_ID",
        "appId": "FIREBASE_APP_ID",
        "databaseURL": "FIREBASE_DATABASE_URL",
        "storageBucket": "FIREBASE_STORAGE_BUCKET",
        "messagingSenderId": "FIREBASE_MESSAGING_SENDER_ID",
    }
    web_config = {
        public_name: value
        for public_name, env_name in config_fields.items()
        if (value := os.getenv(env_name))
    }
    required_fields = {"apiKey", "authDomain", "projectId", "appId"}
    if not required_fields.issubset(web_config):
        return None
    return web_config


def _load_user_from_store(username: str) -> Optional[dict[str, Any]]:
    if not _firebase_user_store_enabled():
        return None
    invalid_key_chars = {".", "#", "$", "[", "]", "/"}
    if any(char in username for char in invalid_key_chars):
        return None
    try:
        user_record = firebase_db.reference(f"{USER_STORE_PATH}/{username}").get()
        if isinstance(user_record, dict):
            fake_users_db[username] = user_record
            return user_record
    except Exception as exc:
        print(f"Error al cargar usuario desde Firebase: {exc}")
    return None


def _load_all_users_from_store() -> None:
    if not _firebase_user_store_enabled():
        return
    try:
        users = firebase_db.reference(USER_STORE_PATH).get()
        if isinstance(users, dict):
            for username, user_record in users.items():
                if isinstance(user_record, dict):
                    fake_users_db[str(username)] = user_record
    except Exception as exc:
        print(f"Error al listar usuarios desde Firebase: {exc}")


def _find_cached_user_by_firebase_identity(uid: str, email: Optional[str]) -> Optional[dict[str, Any]]:
    normalized_email = email.strip().lower() if email else None
    for user_record in fake_users_db.values():
        record_uid = str(user_record.get("uid", "")).strip()
        record_email = str(user_record.get("email", "")).strip().lower()
        if record_uid and record_uid == uid:
            return user_record
        if normalized_email and record_email and record_email == normalized_email:
            return user_record
    return None


def _build_bootstrap_admin_from_firebase_identity(uid: str, email: Optional[str]) -> Optional[dict[str, Any]]:
    admin_uid = os.getenv("ADMIN_FIREBASE_UID", "").strip()
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    token_email = email.strip().lower() if email else ""

    if not admin_uid and not admin_email:
        return None
    if uid != admin_uid and token_email != admin_email:
        return None

    admin_username = _get_required_env("ADMIN_USERNAME")
    admin_record = {
        "uid": uid,
        "username": admin_username,
        "full_name": os.getenv("ADMIN_FULL_NAME", "Admin Safyra"),
        "email": email or os.getenv("ADMIN_EMAIL", ""),
        "role": _validate_role(os.getenv("ADMIN_ROLE", "admin")),
        "status": _validate_account_status(os.getenv("ADMIN_STATUS", ACTIVE_STATUS)),
        "disabled": os.getenv("ADMIN_DISABLED", "false").lower() == "true",
        "hashed_password": "",
        "auth_provider": "firebase",
    }
    fake_users_db[admin_username] = admin_record
    return admin_record


def get_user_by_firebase_identity(uid: str, email: Optional[str]) -> Optional[UserInDB]:
    user_record = _find_cached_user_by_firebase_identity(uid, email)
    if user_record:
        if not user_record.get("uid"):
            user_record["uid"] = uid
        if email and str(user_record.get("email", "")).strip().lower() != email.strip().lower():
            user_record["email"] = email
        user_record["auth_provider"] = "firebase"
        return UserInDB(**user_record)

    _load_all_users_from_store()
    user_record = _find_cached_user_by_firebase_identity(uid, email)
    if user_record:
        if not user_record.get("uid"):
            user_record["uid"] = uid
        if email and str(user_record.get("email", "")).strip().lower() != email.strip().lower():
            user_record["email"] = email
        user_record["auth_provider"] = "firebase"
        return UserInDB(**user_record)

    user_record = _build_bootstrap_admin_from_firebase_identity(uid, email)
    if user_record:
        return UserInDB(**user_record)

    return None


def _save_user_to_store(username: str, user_record: Mapping[str, Any]) -> None:
    if not _firebase_user_store_enabled():
        return
    try:
        firebase_db.reference(f"{USER_STORE_PATH}/{username}").set(dict(user_record))
    except Exception as exc:
        raise RuntimeError(f"Error al guardar usuario en Firebase: {exc}") from exc


def _safe_firebase_child_key(value: str) -> bool:
    return not any(char in value for char in {".", "#", "$", "[", "]", "/"})


def _load_consent_records(username: str) -> list[dict[str, Any]]:
    cached_records = fake_consent_db.get(username, [])
    if not _firebase_consent_store_enabled() or not _safe_firebase_child_key(username):
        return cached_records

    try:
        data = firebase_db.reference(f"{TERMS_CONSENT_STORE_PATH}/{username}").get()
        if isinstance(data, dict):
            records = [record for record in data.values() if isinstance(record, dict)]
            records.sort(key=lambda record: str(record.get("accepted_at", "")))
            fake_consent_db[username] = records
            return records
        fake_consent_db[username] = []
        return []
    except Exception as exc:
        print(f"Error al cargar consentimientos desde Firebase: {exc}")
        fake_consent_db[username] = []
        return []


def _append_consent_record(user: UserInDB, terms_version: str) -> dict[str, Any]:
    record = {
        "username": user.username,
        "uid": user.uid or "",
        "role": user.role,
        "terms_version": terms_version,
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "event_type": "terms_acceptance",
    }

    fake_consent_db.setdefault(user.username, []).append(record)

    if _firebase_consent_store_enabled() and _safe_firebase_child_key(user.username):
        try:
            firebase_db.reference(f"{TERMS_CONSENT_STORE_PATH}/{user.username}").push(record)
        except Exception as exc:
            fake_consent_db[user.username].pop()
            raise RuntimeError(f"Error al guardar consentimiento en Firebase: {exc}") from exc

    return record


def _terms_required_for_user(user: UserInDB) -> bool:
    return user.role in TERMS_REQUIRED_ROLES


def _latest_current_consent(user: UserInDB) -> Optional[dict[str, Any]]:
    records = _load_consent_records(user.username)
    current_records = [
        record for record in records
        if str(record.get("terms_version", "")) == TERMS_VERSION
        and str(record.get("event_type", "terms_acceptance")) == "terms_acceptance"
    ]
    if not current_records:
        return None
    return max(current_records, key=lambda record: str(record.get("accepted_at", "")))


def get_consent_status_for_user(user: UserInDB) -> ConsentStatus:
    requires_acceptance = _terms_required_for_user(user)
    latest_record = _latest_current_consent(user) if requires_acceptance else None
    accepted = not requires_acceptance or latest_record is not None
    return ConsentStatus(
        requires_acceptance=requires_acceptance,
        accepted=accepted,
        terms_version=TERMS_VERSION,
        accepted_version=str(latest_record.get("terms_version")) if latest_record else None,
        accepted_at=str(latest_record.get("accepted_at")) if latest_record else None,
    )


def ensure_current_terms_accepted(user: UserInDB) -> None:
    consent_status = get_consent_status_for_user(user)
    if consent_status.requires_acceptance and not consent_status.accepted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debe aceptar los terminos y condiciones vigentes antes de acceder al sistema",
        )


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db: Mapping[str, dict[str, Any]], username: str) -> Optional[UserInDB]:
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    user_dict = _load_user_from_store(username)
    if user_dict:
        return UserInDB(**user_dict)
    return None


def is_active_user(user: UserInDB) -> bool:
    return user.status == ACTIVE_STATUS and user.disabled is not True


def _is_active_admin_record(user_record: Mapping[str, Any]) -> bool:
    return (
        str(user_record.get("role", "")).strip().lower() == "admin"
        and str(user_record.get("status", ACTIVE_STATUS)).strip().lower() == ACTIVE_STATUS
        and user_record.get("disabled") is not True
    )


def _count_active_admins() -> int:
    _load_all_users_from_store()
    return sum(1 for user_record in fake_users_db.values() if _is_active_admin_record(user_record))


def create_access_token(data: dict[str, str], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def _get_user_from_firebase_token(token: str) -> Optional[UserInDB]:
    if not _firebase_auth_enabled():
        return None
    try:
        decoded_token = firebase_auth.verify_id_token(
            token,
            check_revoked=CHECK_FIREBASE_TOKEN_REVOKED,
        )
    except Exception:
        return None

    uid = str(decoded_token.get("uid") or decoded_token.get("sub") or "").strip()
    if not uid:
        return None

    email = decoded_token.get("email")
    user = get_user_by_firebase_identity(uid=uid, email=str(email) if email else None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario autenticado sin perfil autorizado",
        )
    return user


# Dependencia para obtener el usuario actual
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    firebase_user = _get_user_from_firebase_token(token)
    if firebase_user:
        if not is_active_user(firebase_user):
            raise credentials_exception
        return firebase_user

    if not ALLOW_LEGACY_PASSWORD_LOGIN:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=payload.get("role"))
    except JWTError:
        raise credentials_exception
    
    user = get_user(fake_users_db, username=token_data.username)
    if user is None or not is_active_user(user):
        raise credentials_exception
    return user


def require_roles(*allowed_roles: str) -> Callable[[UserInDB], UserInDB]:
    normalized_allowed_roles = {_validate_role(role) for role in allowed_roles}

    async def role_checker(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if current_user.role not in normalized_allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para acceder a este recurso",
            )
        ensure_current_terms_accepted(current_user)
        return current_user

    return role_checker


def _create_firebase_auth_account(user_data: UserCreate, account_status: str) -> Optional[str]:
    if not _firebase_auth_user_management_enabled():
        return None
    if not user_data.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El correo es obligatorio para crear usuarios con Firebase Auth",
        )
    try:
        user_record = firebase_auth.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.full_name or None,
            disabled=account_status != ACTIVE_STATUS,
        )
        return user_record.uid
    except firebase_auth.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya existe en Firebase Auth") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear usuario en Firebase Auth: {exc}",
        ) from exc


def _update_firebase_auth_account(uid: Optional[str], update_data: dict[str, Any]) -> None:
    if not uid or not update_data or not _firebase_auth_user_management_enabled():
        return
    try:
        firebase_auth.update_user(uid, **update_data)
    except firebase_auth.UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en Firebase Auth") from exc
    except firebase_auth.EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya existe en Firebase Auth") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar usuario en Firebase Auth: {exc}",
        ) from exc

# --- Endpoints ---
@router.get("/auth/config", response_model=AuthConfig)
async def read_auth_config() -> AuthConfig:
    return AuthConfig(
        provider=AUTH_PROVIDER,
        firebase_web_config=_get_firebase_web_config(),
        legacy_password_login_enabled=ALLOW_LEGACY_PASSWORD_LOGIN,
    )


@router.post("/auth/firebase/session", response_model=FirebaseSession)
async def create_firebase_session(current_user: UserInDB = Depends(get_current_user)) -> FirebaseSession:
    return FirebaseSession(token_type="bearer", user=_public_user_from_model(current_user))


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> dict[str, str]:
    """
    Endpoint de login local legacy. En producción se debe usar Firebase Auth.
    """
    if not ALLOW_LEGACY_PASSWORD_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Login local deshabilitado. Use Firebase Auth.",
        )

    user = get_user(fake_users_db, form_data.username)
    if not user or not is_active_user(user) or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "username": user.username, "role": user.role}


@router.get("/users/me", response_model=User)
async def read_current_user_profile(current_user: UserInDB = Depends(get_current_user)) -> User:
    return _public_user_from_model(current_user)


@router.get("/consent/status", response_model=ConsentStatus)
async def read_consent_status(current_user: UserInDB = Depends(get_current_user)) -> ConsentStatus:
    return get_consent_status_for_user(current_user)


@router.post("/consent/accept", response_model=ConsentRecord, status_code=status.HTTP_201_CREATED)
async def accept_terms(
    consent_data: ConsentAcceptRequest,
    current_user: UserInDB = Depends(get_current_user),
) -> ConsentRecord:
    requested_version = consent_data.terms_version or TERMS_VERSION
    if requested_version != TERMS_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La version de terminos enviada no coincide con la version vigente",
        )

    try:
        record = _append_consent_record(current_user, TERMS_VERSION)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ConsentRecord(**record)


@router.get("/admin/users", response_model=list[User])
async def list_users(_: UserInDB = Depends(require_roles("admin"))) -> list[User]:
    _load_all_users_from_store()
    return [_public_user_from_record(user_record) for user_record in fake_users_db.values()]


@router.post("/admin/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, _: UserInDB = Depends(require_roles("admin"))) -> User:
    username = _normalize_username(user_data.username)
    if username in fake_users_db or _load_user_from_store(username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El usuario ya existe")

    role = _parse_role_for_request(user_data.role)
    account_status = _parse_status_for_request(user_data.status)
    firebase_uid = _create_firebase_auth_account(user_data, account_status)
    should_store_local_password = firebase_uid is None

    fake_users_db[username] = {
        "uid": firebase_uid or "",
        "username": username,
        "email": user_data.email or "",
        "full_name": user_data.full_name or "",
        "role": role,
        "status": account_status,
        "disabled": account_status != ACTIVE_STATUS,
        "hashed_password": pwd_context.hash(user_data.password) if should_store_local_password else "",
        "auth_provider": "firebase" if firebase_uid else "local",
    }
    try:
        _save_user_to_store(username, fake_users_db[username])
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return _public_user_from_record(fake_users_db[username])


@router.patch("/admin/users/{username}", response_model=User)
async def update_user(
    username: str,
    user_data: UserUpdate,
    _: UserInDB = Depends(require_roles("admin")),
) -> User:
    normalized_username = _normalize_username(username)
    if normalized_username not in fake_users_db:
        _load_user_from_store(normalized_username)
    if normalized_username not in fake_users_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    user_record = fake_users_db[normalized_username]
    requested_role = _parse_role_for_request(user_data.role) if user_data.role is not None else str(user_record["role"])
    requested_status = (
        _parse_status_for_request(user_data.status)
        if user_data.status is not None
        else str(user_record.get("status", ACTIVE_STATUS))
    )
    would_remain_active_admin = requested_role == "admin" and requested_status == ACTIVE_STATUS
    if _is_active_admin_record(user_record) and not would_remain_active_admin and _count_active_admins() <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede dejar el sistema sin un administrador activo",
        )

    firebase_update_data: dict[str, Any] = {}
    if user_data.email is not None:
        firebase_update_data["email"] = user_data.email
        user_record["email"] = user_data.email
    if user_data.full_name is not None:
        firebase_update_data["display_name"] = user_data.full_name
        user_record["full_name"] = user_data.full_name
    if user_data.role is not None:
        user_record["role"] = requested_role
    if user_data.status is not None:
        user_record["status"] = requested_status
        user_record["disabled"] = requested_status != ACTIVE_STATUS
        firebase_update_data["disabled"] = requested_status != ACTIVE_STATUS
    if user_data.password is not None:
        if user_record.get("uid"):
            firebase_update_data["password"] = user_data.password
            user_record["hashed_password"] = ""
            user_record["auth_provider"] = "firebase"
        else:
            user_record["hashed_password"] = pwd_context.hash(user_data.password)

    _update_firebase_auth_account(user_record.get("uid"), firebase_update_data)

    try:
        _save_user_to_store(normalized_username, user_record)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return _public_user_from_record(user_record)
