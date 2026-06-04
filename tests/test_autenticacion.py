# tests/test_autenticacion.py
"""
Pruebas unitarias para el sistema de autenticaciÃ³n
Endpoint: POST /token
"""

import pytest
import os
import secrets
from jose import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app.routers.auth_api import (
    SECRET_KEY,
    ALGORITHM,
    TERMS_VERSION,
    create_access_token,
    fake_consent_db,
    fake_users_db,
    pwd_context,
)

TEST_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
TEST_ADMIN_PASSWORD = os.environ["TEST_ADMIN_PASSWORD"]
INVALID_TEST_PASSWORD = secrets.token_urlsafe(24)
SPECIAL_INVALID_TEST_PASSWORD = f"{secrets.token_urlsafe(18)}!#%"


@pytest.mark.autenticacion
class TestLoginExitoso:
    """Escenarios de login exitoso"""
    
    def test_login_credenciales_correctas(self, test_client):
        """
        Escenario: Usuario ingresa credenciales correctas
        Dado: Usuario admin de prueba configurado por entorno
        Cuando: Se envÃ­a POST /token con las credenciales
        Entonces: Se retorna token JWT vÃ¡lido
        """
        response = test_client.post(
            "/token",
            data={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        # Verificar que el token es vÃ¡lido
        token = data["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == TEST_ADMIN_USERNAME
        assert payload["role"] == "admin"
        assert data["role"] == "admin"
    
    def test_token_contiene_expiracion(self, test_client):
        """
        Escenario: Token generado contiene fecha de expiraciÃ³n
        Dado: Login exitoso
        Cuando: Se decodifica el token
        Entonces: Contiene campo "exp" con fecha futura
        """
        response = test_client.post(
            "/token",
            data={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD}
        )
        
        token = response.json()["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        assert "exp" in payload
        
        # Usar timezone-aware datetime para comparaciÃ³n correcta
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Verificar que el token expira en el futuro
        assert exp_time > now, f"Token ya expirÃ³: {exp_time} <= {now}"
        
        # Verificar que la expiraciÃ³n es razonable (entre 1 min y 2 aÃ±os)
        time_diff = exp_time - now
        assert timedelta(minutes=1) < time_diff < timedelta(days=730), \
            f"Tiempo de expiraciÃ³n no razonable: {time_diff}"


@pytest.mark.autenticacion
class TestLoginFallido:
    """Escenarios de login fallido"""
    
    def test_credenciales_incorrectas(self, test_client):
        """
        Escenario: Usuario con contraseÃ±a incorrecta
        Dado: Usuario admin con contraseÃ±a incorrecta aleatoria
        Cuando: Se intenta login
        Entonces: Se retorna error 401
        """
        response = test_client.post(
            "/token",
            data={"username": TEST_ADMIN_USERNAME, "password": INVALID_TEST_PASSWORD}
        )
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_usuario_inexistente(self, test_client):
        """
        Escenario: Usuario no existe en la base de datos
        Dado: Usuario "hacker" que no estÃ¡ registrado
        Cuando: Se intenta login
        Entonces: Se retorna error 401
        """
        response = test_client.post(
            "/token",
            data={"username": "hacker", "password": INVALID_TEST_PASSWORD}
        )
        
        assert response.status_code == 401
    
    def test_campos_vacios(self, test_client):
        """
        Escenario: Campos de login vacÃ­os
        Dado: Username o password vacÃ­o
        Cuando: Se intenta login
        Entonces: Se retorna error 401 (credenciales invÃ¡lidas)
        
        Nota: FastAPI OAuth2PasswordRequestForm no valida campos vacÃ­os
        como error 422, sino que los trata como credenciales incorrectas (401)
        """
        response = test_client.post(
            "/token",
            data={"username": "", "password": ""}
        )
        
        # El comportamiento actual es 401, no 422
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.autenticacion
class TestProteccionEndpoints:
    """Pruebas de protecciÃ³n de endpoints con JWT"""

    def test_auth_config_no_expone_secretos(self, test_client):
        """
        Escenario: Frontend solicita configuracion publica de autenticacion
        Entonces: No se exponen secretos del backend ni credenciales privadas
        """
        response = test_client.get("/auth/config")

        assert response.status_code == 200
        response_text = response.text
        assert "JWT_SECRET_KEY" not in response_text
        assert "ADMIN_PASSWORD" not in response_text
        assert "FIREBASE_PRIVATE_KEY" not in response_text
    
    def test_acceso_sin_token(self, test_client):
        """
        Escenario: Intento de acceso sin token
        Dado: No se envÃ­a header de autorizaciÃ³n
        Cuando: Se accede a endpoint protegido
        Entonces: Se retorna error 401
        """
        response = test_client.get("/api/data/current")
        
        assert response.status_code == 401
    
    def test_acceso_token_invalido(self, test_client):
        """
        Escenario: Token JWT malformado
        Dado: Token invÃ¡lido en header
        Cuando: Se intenta acceder
        Entonces: Se retorna error 401
        """
        headers = {"Authorization": "Bearer token_invalido"}
        response = test_client.get("/api/data/current", headers=headers)
        
        assert response.status_code == 401
    
    def test_acceso_token_expirado(self, test_client):
        """
        Escenario: Token JWT expirado
        Dado: Token con fecha de expiraciÃ³n pasada
        Cuando: Se intenta usar el token
        Entonces: Se retorna error 401
        """
        # Crear token expirado (usando timezone-aware datetime)
        expired_data = {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1)
        }
        expired_token = jwt.encode(expired_data, SECRET_KEY, algorithm=ALGORITHM)
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = test_client.get("/api/data/current", headers=headers)
        
        assert response.status_code == 401
    
    def test_acceso_token_valido(self, test_client, headers_autenticados):
        """
        Escenario: Acceso con token vÃ¡lido
        Dado: Token JWT vÃ¡lido y no expirado
        Cuando: Se accede a endpoint protegido
        Entonces: Se permite el acceso
        """
        # OpciÃ³n 1: Mock directo en el router (recomendado)
        with patch('app.routers.data_api.get_current_data') as mock_get:
            mock_get.return_value = {
                "sensors": [],
                "connected": False,
                "message": "Sin dispositivos",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_consumption": 0.0
            }
            
            response = test_client.get("/api/data/current", headers=headers_autenticados)
            
            assert response.status_code == 200
            data = response.json()
            assert "sensors" in data
            assert "connected" in data
            assert isinstance(data["sensors"], list)
            
            # Verificar que la funciÃ³n fue llamada
            mock_get.assert_called_once()

    def test_acceso_con_firebase_id_token_valido(self, test_client):
        """
        Escenario: Backend valida ID token de Firebase Auth
        Entonces: Se usa el perfil autorizado guardado por uid/rol
        """
        username = f"firebase_{secrets.token_hex(4)}"
        uid = f"uid_{secrets.token_hex(8)}"
        fake_users_db[username] = {
            "uid": uid,
            "username": username,
            "full_name": "Usuario Firebase",
            "email": f"{username}@example.test",
            "role": "admin",
            "status": "activo",
            "disabled": False,
            "hashed_password": "",
            "auth_provider": "firebase",
        }

        try:
            with patch("app.routers.auth_api._firebase_auth_enabled", return_value=True), patch(
                "app.routers.auth_api.firebase_auth.verify_id_token",
                return_value={"uid": uid, "email": f"{username}@example.test"},
            ):
                response = test_client.get("/users/me", headers={"Authorization": "Bearer firebase-id-token"})

            assert response.status_code == 200
            data = response.json()
            assert data["username"] == username
            assert data["role"] == "admin"
            assert data["auth_provider"] == "firebase"
        finally:
            fake_users_db.pop(username, None)

    def test_firebase_id_token_sin_perfil_no_accede(self, test_client):
        """
        Escenario: Firebase Auth autentica, pero no existe perfil con rol
        Entonces: Se bloquea el acceso por falta de autorizacion interna
        """
        with patch("app.routers.auth_api._firebase_auth_enabled", return_value=True), patch(
            "app.routers.auth_api.firebase_auth.verify_id_token",
            return_value={"uid": f"uid_{secrets.token_hex(8)}", "email": "sin_rol@example.test"},
        ):
            response = test_client.get("/users/me", headers={"Authorization": "Bearer firebase-id-token"})

        assert response.status_code == 403

    def test_perfil_usuario_actual_incluye_rol(self, test_client, headers_autenticados):
        """
        Escenario: Usuario autenticado consulta su perfil
        Entonces: Se retorna rol y estado sin exponer hash de password
        """
        response = test_client.get("/users/me", headers=headers_autenticados)

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == TEST_ADMIN_USERNAME
        assert data["role"] == "admin"
        assert data["status"] == "activo"
        assert "hashed_password" not in data

    def test_auditor_puede_ver_dashboard_actual(self, test_client, headers_auditor):
        """
        Escenario: Rol auditor accede al dashboard de monitoreo
        Entonces: Se permite solo lectura operativa
        """
        with patch('app.routers.data_api.get_current_data') as mock_get:
            mock_get.return_value = {
                "sensors": [],
                "connected": False,
                "message": "Sin dispositivos",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_consumption": 0.0
            }

            response = test_client.get("/api/data/current", headers=headers_auditor)

            assert response.status_code == 200
            mock_get.assert_called_once()


    def test_auditor_no_puede_actualizar_umbral(self, test_client, headers_auditor):
        """
        Escenario: Rol auditor intenta modificar configuraciÃ³n crÃ­tica
        Entonces: El backend bloquea la operaciÃ³n
        """
        response = test_client.put(
            "/api/data/threshold/LAB-PC-01",
            json={"corriente": 11.0, "potencia": 2420.0},
            headers=headers_auditor
        )

        assert response.status_code == 403

    def test_usuario_congelado_no_puede_acceder(self, test_client, headers_congelado):
        """
        Escenario: Usuario con estado congelado intenta usar su token
        Entonces: El sistema rechaza la autenticaciÃ³n
        """
        response = test_client.get("/api/data/current", headers=headers_congelado)

        assert response.status_code == 401


@pytest.mark.autenticacion
class TestConsentimientoTyC:
    """Pruebas del flujo de TyC y registro de consentimiento"""

    def _crear_usuario_activo_sin_consentimiento(self) -> tuple[str, dict[str, str]]:
        username = f"tyc_{secrets.token_hex(4)}"
        fake_users_db[username] = {
            "username": username,
            "full_name": "Usuario TyC",
            "email": f"{username}@example.test",
            "role": "auditor",
            "status": "activo",
            "disabled": False,
            "hashed_password": pwd_context.hash(secrets.token_urlsafe(24)),
        }
        fake_consent_db.pop(username, None)
        token = create_access_token(data={"sub": username, "role": "auditor"})
        return username, {"Authorization": f"Bearer {token}"}

    def test_tyc_pendiente_bloquea_endpoint_protegido(self, test_client):
        username, headers = self._crear_usuario_activo_sin_consentimiento()

        try:
            status_response = test_client.get("/consent/status", headers=headers)
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["requires_acceptance"] is True
            assert status_data["accepted"] is False
            assert status_data["terms_version"] == TERMS_VERSION

            protected_response = test_client.get("/api/data/current", headers=headers)
            assert protected_response.status_code == 403
            assert "terminos" in protected_response.json()["detail"]
        finally:
            fake_users_db.pop(username, None)
            fake_consent_db.pop(username, None)

    def test_aceptar_tyc_registra_usuario_fecha_y_version(self, test_client):
        username, headers = self._crear_usuario_activo_sin_consentimiento()

        try:
            response = test_client.post(
                "/consent/accept",
                headers=headers,
                json={"terms_version": TERMS_VERSION},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["username"] == username
            assert data["role"] == "auditor"
            assert data["terms_version"] == TERMS_VERSION
            assert data["accepted_at"]
            assert "hashed_password" not in data

            assert fake_consent_db[username][-1]["terms_version"] == TERMS_VERSION

            status_response = test_client.get("/consent/status", headers=headers)
            status_data = status_response.json()
            assert status_data["accepted"] is True
            assert status_data["accepted_version"] == TERMS_VERSION
        finally:
            fake_users_db.pop(username, None)
            fake_consent_db.pop(username, None)

    def test_consentimiento_borrado_en_firebase_no_se_acepta_por_cache(self, test_client):
        username, headers = self._crear_usuario_activo_sin_consentimiento()
        fake_consent_db[username] = [{
            "username": username,
            "role": "auditor",
            "terms_version": TERMS_VERSION,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "event_type": "terms_acceptance",
        }]

        try:
            with patch("app.routers.auth_api._firebase_consent_store_enabled", return_value=True), patch(
                "app.routers.auth_api.firebase_db.reference"
            ) as mock_reference:
                mock_reference.return_value.get.return_value = None

                status_response = test_client.get("/consent/status", headers=headers)
                protected_response = test_client.get("/api/data/current", headers=headers)

            assert status_response.status_code == 200
            assert status_response.json()["accepted"] is False
            assert protected_response.status_code == 403
            assert fake_consent_db[username] == []
        finally:
            fake_users_db.pop(username, None)
            fake_consent_db.pop(username, None)


@pytest.mark.autenticacion
class TestSeguridadPassword:
    """Pruebas de seguridad de contraseÃ±as"""
    
    def test_password_hasheado(self):
        """
        Escenario: Verificar que contraseÃ±as estÃ¡n hasheadas
        Dado: Sistema de autenticaciÃ³n
        Cuando: Se verifica la base de datos
        Entonces: ContraseÃ±as no estÃ¡n en texto plano
        """
        from app.routers.auth_api import fake_users_db
        
        for user_data in fake_users_db.values():
            if user_data.get("auth_provider") == "firebase":
                assert not user_data.get("hashed_password")
                continue
            # La contraseÃ±a hasheada debe comenzar con $2b$ (bcrypt)
            assert user_data["hashed_password"].startswith("$2b$")
            # Debe tener longitud de hash bcrypt (60 caracteres)
            assert len(user_data["hashed_password"]) == 60
    
    def test_inyeccion_sql_username(self, test_client):
        """
        Escenario: Intento de inyecciÃ³n SQL en username
        Dado: Username con caracteres de inyecciÃ³n SQL
        Cuando: Se intenta login
        Entonces: Sistema maneja correctamente sin vulnerabilidad
        """
        response = test_client.post(
            "/token",
            data={"username": "admin' OR '1'='1", "password": INVALID_TEST_PASSWORD}
        )
        
        # No debe permitir acceso
        assert response.status_code == 401
        
    def test_password_con_caracteres_especiales(self, test_client):
        """
        Escenario: ContraseÃ±a con caracteres especiales
        Dado: Password con sÃ­mbolos y espacios
        Cuando: Se intenta login
        Entonces: Sistema maneja correctamente
        """
        response = test_client.post(
            "/token",
            data={"username": TEST_ADMIN_USERNAME, "password": SPECIAL_INVALID_TEST_PASSWORD}
        )
        
        # Debe rechazar (no es la contraseÃ±a correcta)
        assert response.status_code == 401


@pytest.mark.autenticacion
class TestGestionUsuarios:
    """Pruebas de gestiÃ³n administrativa de usuarios, roles y estados"""

    def test_admin_lista_usuarios_sin_hash_password(self, test_client, headers_autenticados):
        response = test_client.get("/admin/users", headers=headers_autenticados)

        assert response.status_code == 200
        users = response.json()
        assert any(user["username"] == TEST_ADMIN_USERNAME for user in users)
        assert all("hashed_password" not in user for user in users)

    def test_auditor_no_puede_listar_usuarios(self, test_client, headers_auditor):
        response = test_client.get("/admin/users", headers=headers_auditor)

        assert response.status_code == 403

    def test_admin_crea_usuario_auditor(self, test_client, headers_autenticados):
        username = f"auditor_{secrets.token_hex(4)}"
        password = secrets.token_urlsafe(24)

        response = test_client.post(
            "/admin/users",
            headers=headers_autenticados,
            json={
                "username": username,
                "password": password,
                "role": "auditor",
                "status": "activo",
                "email": f"{username}@example.test",
                "full_name": "Usuario auditor Nuevo",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == username
        assert data["role"] == "auditor"
        assert data["status"] == "activo"
        assert "hashed_password" not in data

        login_response = test_client.post(
            "/token",
            data={"username": username, "password": password},
        )
        assert login_response.status_code == 200
        assert login_response.json()["role"] == "auditor"

    def test_no_hay_registro_publico_para_crear_usuarios(self, test_client):
        username = f"auditor_{secrets.token_hex(4)}"
        response = test_client.post(
            "/admin/users",
            json={
                "username": username,
                "password": secrets.token_urlsafe(24),
                "role": "auditor",
                "status": "activo",
            },
        )

        assert response.status_code == 401

    def test_admin_cambia_rol_y_estado_sin_borrar_usuario(self, test_client, headers_autenticados):
        username = f"estado_{secrets.token_hex(4)}"
        password = secrets.token_urlsafe(24)

        create_response = test_client.post(
            "/admin/users",
            headers=headers_autenticados,
            json={
                "username": username,
                "password": password,
                "role": "auditor",
                "status": "activo",
            },
        )
        assert create_response.status_code == 201

        update_response = test_client.patch(
            f"/admin/users/{username}",
            headers=headers_autenticados,
            json={
                "role": "auditor",
                "status": "congelado",
            },
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["username"] == username
        assert data["role"] == "auditor"
        assert data["status"] == "congelado"
        assert data["disabled"] is True

        login_response = test_client.post(
            "/token",
            data={"username": username, "password": password},
        )
        assert login_response.status_code == 401

        list_response = test_client.get("/admin/users", headers=headers_autenticados)
        users = list_response.json()
        assert any(user["username"] == username and user["status"] == "congelado" for user in users)

    def test_admin_no_puede_dejar_sistema_sin_admin_activo(self, test_client, headers_autenticados):
        response = test_client.patch(
            f"/admin/users/{TEST_ADMIN_USERNAME}",
            headers=headers_autenticados,
            json={"role": "auditor"},
        )

        assert response.status_code == 400
        assert "administrador activo" in response.json()["detail"]

    def test_admin_no_puede_crear_usuario_duplicado(self, test_client, headers_autenticados):
        username = f"duplicado_{secrets.token_hex(4)}"
        payload = {
            "username": username,
            "password": secrets.token_urlsafe(24),
            "role": "auditor",
            "status": "activo",
        }

        first_response = test_client.post("/admin/users", headers=headers_autenticados, json=payload)
        second_response = test_client.post("/admin/users", headers=headers_autenticados, json=payload)

        assert first_response.status_code == 201
        assert second_response.status_code == 409

    def test_admin_no_puede_asignar_rol_invalido(self, test_client, headers_autenticados):
        response = test_client.post(
            "/admin/users",
            headers=headers_autenticados,
            json={
                "username": f"invalido_{secrets.token_hex(4)}",
                "password": secrets.token_urlsafe(24),
                "role": "superusuario",
                "status": "activo",
            },
        )

        assert response.status_code == 422
