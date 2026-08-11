# 4. Requisitos del proyecto

> Fuente: `docs/superpowers/specs/2026-08-11-memoria-cap4-requisitos-design.md` (diseño aprobado).
> Casos de uso derivados directamente del inventario de rutas en `backend/app/api/`, no de la
> lista original de `memoria-ada-outline.md` §4 (que agrupaba un paso interno del sistema —
> detección de pose — como si fuera una acción propia del usuario).

## Requisitos funcionales (casos de uso)

### CU-1: Registrarse

- **Actor:** Usuario no autenticado.
- **Precondición:** El usuario dispone de un email no registrado previamente y una contraseña.
- **Flujo principal:**
  1. El usuario introduce email y contraseña en el formulario de registro.
  2. El sistema valida el formato del email y la fortaleza de la contraseña.
  3. El sistema crea la cuenta y genera un par de tokens (access + refresh).
  4. El sistema devuelve los tokens; el usuario queda autenticado de inmediato.
- **Postcondición:** Existe una nueva cuenta de usuario en la base de datos; el usuario tiene una
  sesión activa.
- **Fuente:** `POST /v1/auth/register` (`backend/app/api/auth.py`).

### CU-2: Iniciar sesión

- **Actor:** Usuario registrado.
- **Precondición:** El usuario posee una cuenta existente con credenciales válidas.
- **Flujo principal:**
  1. El usuario introduce email y contraseña.
  2. El sistema valida las credenciales contra el hash almacenado.
  3. El sistema emite un nuevo par de tokens (access + refresh).
- **Postcondición:** El usuario queda autenticado. Un token de refresco emitido en una sesión
  anterior no se invalida por este nuevo login — coexisten hasta que cada uno se use o se revoque.
- **Fuente:** `POST /v1/auth/login` (`backend/app/api/auth.py`).

### CU-3: Cerrar sesión

- **Actor:** Usuario autenticado.
- **Precondición:** El usuario tiene una sesión activa con un token de refresco válido.
- **Flujo principal:**
  1. El usuario solicita cerrar sesión.
  2. El sistema revoca el token de refresco actual en la base de datos.
  3. El cliente descarta el access token en memoria y el refresh token en `localStorage`.
- **Postcondición:** El token de refresco queda revocado; cualquier intento posterior de usarlo
  para renovar la sesión es rechazado.
- **Fuente:** `POST /v1/auth/logout` (`backend/app/api/auth.py`).

### CU-4: Subir video de un intento

- **Actor:** Usuario autenticado; Sistema (cv-service), de forma asíncrona.
- **Precondición:** El usuario está autenticado y dispone de un video (`.mp4` o `.mov`, ≤100MB,
  ≤60s).
- **Flujo principal:**
  1. El usuario selecciona o graba un video y lo sube desde el formulario de carga.
  2. El backend valida extensión, tamaño y duración del archivo.
  3. El backend crea el intento (estado "pendiente") y lo reenvía a cv-service.
  4. cv-service procesa el video de forma asíncrona (detección de pose, conteo de repeticiones,
     scoring) y notifica el resultado al backend mediante un webhook firmado (HMAC-SHA256).
  5. El backend actualiza el intento a "completado" (o "fallido") con el resultado.
- **Postcondición:** Existe un nuevo intento asociado al usuario, con estado y resultado (cuando
  termina el análisis) persistidos en la base de datos.
- **Fuente:** `POST /v1/attempts` (`backend/app/api/attempts.py`); webhook callback firmado.

### CU-5: Consultar resultado de un intento

- **Actor:** Usuario autenticado.
- **Precondición:** El usuario tiene al menos un intento propio, en cualquier estado.
- **Flujo principal:**
  1. El usuario abre el detalle de uno de sus intentos.
  2. El sistema devuelve el estado del intento y, si está completado, el score por repetición,
     los consejos de mejora y una URL del video anotado.
  3. Si el usuario reproduce el video anotado, el frontend lo solicita a través del endpoint proxy
     autenticado — nunca directamente a cv-service.
- **Postcondición:** El usuario visualiza el score, los consejos y el video anotado de su intento,
  sin que la clave interna de cv-service llegue nunca al navegador.
- **Fuente:** `GET /v1/attempts/{attempt_id}`, `GET /v1/attempts/{attempt_id}/video`
  (`backend/app/api/attempts.py`).

### CU-6: Ver historial de intentos

- **Actor:** Usuario autenticado.
- **Precondición:** El usuario tiene cero o más intentos previos.
- **Flujo principal:**
  1. El usuario abre la vista de historial.
  2. El sistema devuelve la lista paginada de sus intentos, ordenada por fecha, con estado y score
     resumido.
- **Postcondición:** El usuario visualiza la evolución de sus intentos a lo largo del tiempo.
- **Fuente:** `GET /v1/attempts` (`backend/app/api/attempts.py`).

### CU-7: Eliminar un intento (derecho al olvido / GDPR)

- **Actor:** Usuario autenticado.
- **Precondición:** El usuario es propietario de un intento existente.
- **Flujo principal:**
  1. El usuario solicita eliminar un intento concreto.
  2. El backend elimina el intento y su video asociado en su propia base de datos.
  3. El backend solicita a cv-service la eliminación del job y sus archivos (video original y
     anotado).
- **Postcondición:** Ni el backend ni cv-service conservan datos del intento eliminado.
- **Fuente:** `DELETE /v1/attempts/{attempt_id}` (backend); `DELETE /v1/jobs/{id}` (cv-service,
  invocado internamente por el backend).
