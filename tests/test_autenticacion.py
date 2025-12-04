# tests/test_autenticacion.py
"""
Pruebas unitarias para el sistema de autenticación
Endpoint: POST /token
"""

import pytest
from jose import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app.routers.auth_api import SECRET_KEY, ALGORITHM


@pytest.mark.autenticacion
class TestLoginExitoso:
    """Escenarios de login exitoso"""
    
    def test_login_credenciales_correctas(self, test_client):
        """
        Escenario: Usuario ingresa credenciales correctas
        Dado: Usuario "admin" con contraseña "admin123"
        Cuando: Se envía POST /token con las credenciales
        Entonces: Se retorna token JWT válido
        """
        response = test_client.post(
            "/token",
            data={"username": "admin", "password": "admin123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        # Verificar que el token es válido
        token = data["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "admin"
    
    def test_token_contiene_expiracion(self, test_client):
        """
        Escenario: Token generado contiene fecha de expiración
        Dado: Login exitoso
        Cuando: Se decodifica el token
        Entonces: Contiene campo "exp" con fecha futura
        """
        response = test_client.post(
            "/token",
            data={"username": "admin", "password": "admin123"}
        )
        
        token = response.json()["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        assert "exp" in payload
        
        # Usar timezone-aware datetime para comparación correcta
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Verificar que el token expira en el futuro
        assert exp_time > now, f"Token ya expiró: {exp_time} <= {now}"
        
        # Verificar que la expiración es razonable (entre 1 min y 2 años)
        time_diff = exp_time - now
        assert timedelta(minutes=1) < time_diff < timedelta(days=730), \
            f"Tiempo de expiración no razonable: {time_diff}"


@pytest.mark.autenticacion
class TestLoginFallido:
    """Escenarios de login fallido"""
    
    def test_credenciales_incorrectas(self, test_client):
        """
        Escenario: Usuario con contraseña incorrecta
        Dado: Usuario "admin" con contraseña "wrongpass"
        Cuando: Se intenta login
        Entonces: Se retorna error 401
        """
        response = test_client.post(
            "/token",
            data={"username": "admin", "password": "wrongpass"}
        )
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_usuario_inexistente(self, test_client):
        """
        Escenario: Usuario no existe en la base de datos
        Dado: Usuario "hacker" que no está registrado
        Cuando: Se intenta login
        Entonces: Se retorna error 401
        """
        response = test_client.post(
            "/token",
            data={"username": "hacker", "password": "anypass"}
        )
        
        assert response.status_code == 401
    
    def test_campos_vacios(self, test_client):
        """
        Escenario: Campos de login vacíos
        Dado: Username o password vacío
        Cuando: Se intenta login
        Entonces: Se retorna error 401 (credenciales inválidas)
        
        Nota: FastAPI OAuth2PasswordRequestForm no valida campos vacíos
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
    """Pruebas de protección de endpoints con JWT"""
    
    def test_acceso_sin_token(self, test_client):
        """
        Escenario: Intento de acceso sin token
        Dado: No se envía header de autorización
        Cuando: Se accede a endpoint protegido
        Entonces: Se retorna error 401
        """
        response = test_client.get("/api/data/current")
        
        assert response.status_code == 401
    
    def test_acceso_token_invalido(self, test_client):
        """
        Escenario: Token JWT malformado
        Dado: Token inválido en header
        Cuando: Se intenta acceder
        Entonces: Se retorna error 401
        """
        headers = {"Authorization": "Bearer token_invalido"}
        response = test_client.get("/api/data/current", headers=headers)
        
        assert response.status_code == 401
    
    def test_acceso_token_expirado(self, test_client):
        """
        Escenario: Token JWT expirado
        Dado: Token con fecha de expiración pasada
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
        Escenario: Acceso con token válido
        Dado: Token JWT válido y no expirado
        Cuando: Se accede a endpoint protegido
        Entonces: Se permite el acceso
        """
        # Opción 1: Mock directo en el router (recomendado)
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
            
            # Verificar que la función fue llamada
            mock_get.assert_called_once()


@pytest.mark.autenticacion
class TestSeguridadPassword:
    """Pruebas de seguridad de contraseñas"""
    
    def test_password_hasheado(self):
        """
        Escenario: Verificar que contraseñas están hasheadas
        Dado: Sistema de autenticación
        Cuando: Se verifica la base de datos
        Entonces: Contraseñas no están en texto plano
        """
        from app.routers.auth_api import fake_users_db
        
        for user_data in fake_users_db.values():
            # La contraseña hasheada debe comenzar con $2b$ (bcrypt)
            assert user_data["hashed_password"].startswith("$2b$")
            # Debe tener longitud de hash bcrypt (60 caracteres)
            assert len(user_data["hashed_password"]) == 60
    
    def test_inyeccion_sql_username(self, test_client):
        """
        Escenario: Intento de inyección SQL en username
        Dado: Username con caracteres de inyección SQL
        Cuando: Se intenta login
        Entonces: Sistema maneja correctamente sin vulnerabilidad
        """
        response = test_client.post(
            "/token",
            data={"username": "admin' OR '1'='1", "password": "anypass"}
        )
        
        # No debe permitir acceso
        assert response.status_code == 401
        
    def test_password_con_caracteres_especiales(self, test_client):
        """
        Escenario: Contraseña con caracteres especiales
        Dado: Password con símbolos y espacios
        Cuando: Se intenta login
        Entonces: Sistema maneja correctamente
        """
        response = test_client.post(
            "/token",
            data={"username": "admin", "password": "p@ss w0rd!#$%"}
        )
        
        # Debe rechazar (no es la contraseña correcta)
        assert response.status_code == 401