# 4. Requisitos del proyecto

<!--
Fuente: docs/superpowers/specs/2026-08-11-memoria-cap4-requisitos-design.md (diseño aprobado).
Casos de uso derivados directamente del inventario de rutas en backend/app/api/, no de la
lista original de memoria-ada-outline.md §4 (que agrupaba un paso interno del sistema —
detección de pose — como si fuera una acción propia del usuario).
-->

## Requisitos funcionales (casos de uso)

*Los casos de uso describen el comportamiento previsto por el contrato del sistema. Donde la
implementación actual todavía no lo cumple del todo, se indica explícitamente en el propio caso
de uso (ver CU-5).*

### CU-1: Registrarse

- **Actor:** Usuario no autenticado.
- **Precondición:** El usuario dispone de un email no registrado previamente y una contraseña.
- **Flujo principal:**
  1. El usuario introduce email y contraseña en el formulario de registro.
  2. El sistema valida el formato del email y que la contraseña tenga al menos 8 caracteres
     (`min_length=8`, `backend/app/schemas/auth.py`).
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
- **Precondición:** El usuario está autenticado y dispone de un video (`.mp4` o `.mov`, códec
  H.264, ≤100 MB, ≤60s).
- **Flujo principal:**
  1. El usuario selecciona un video y lo sube desde el formulario de carga (subida de archivo;
     no hay grabación en el navegador implementada en el frontend actual).
  2. El backend valida extensión, códec, tamaño y duración del archivo
     (`backend/app/services/validation.py::validate_upload`).
  3. El backend guarda el video en el almacenamiento de archivos y lo envía a cv-service; solo si
     cv-service acepta el job, persiste el intento en la base de datos con estado "en cola"
     (`queued`) (`backend/app/services/attempts.py::create_attempt`).
  4. cv-service procesa el video de forma asíncrona, como `BackgroundTask` de FastAPI dentro de su
     propio proceso (detección de pose, conteo de repeticiones, scoring) y notifica el resultado
     al backend mediante un webhook firmado (HMAC-SHA256). Si el webhook no llega, un
     reconciliador de respaldo en el backend consulta el estado directamente a cv-service pasado
     un tiempo configurado (`backend/app/services/jobs.py::reconcile_stale_attempts`).
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
     los códigos de error de técnica por repetición (previstos en el contrato y ya representados
     en la interfaz, `frontend/src/components/attempt-result.tsx`) y una URL del video anotado.
     **Estado actual:** `cv-service` todavía no emite estos códigos — `pipeline.py` fija
     `"errors": []` en cada repetición — por lo que hoy el usuario ve el score y el video, pero
     ningún consejo de técnica por repetición; esta es la detección de errores de forma pendiente
     de Alejandro.
  3. Si el usuario reproduce el video anotado, el frontend lo solicita a través del endpoint proxy
     autenticado — nunca directamente a cv-service.
- **Postcondición:** El usuario visualiza el score y el video anotado de su intento; los consejos
  de técnica por repetición quedan pendientes de que `cv-service` los emita. La clave interna de
  cv-service nunca llega al navegador.
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
  2. El backend borra el video original del almacenamiento de archivos (`./var/videos`; el video
     nunca vive en la base de datos, solo su referencia).
  3. El backend solicita a cv-service la eliminación del job y sus archivos (video original y
     anotado). Si cv-service no puede confirmar el borrado, el error se propaga y el paso 4 no se
     ejecuta.
  4. Solo si cv-service confirma, el backend borra la fila del intento en la base de datos.
- **Postcondición:** Si cv-service confirma el borrado, ni el backend ni cv-service conservan
  datos del intento. Si cv-service falla, la fila del intento se conserva (aunque el video local
  ya se haya eliminado en el paso 2) para que el usuario pueda reintentar la eliminación.
- **Fuente:** `DELETE /v1/attempts/{attempt_id}` (`backend/app/services/attempts.py::delete_attempt`);
  `DELETE /v1/jobs/{id}` (cv-service, invocado internamente por el backend).

## Requisitos no funcionales

Cada categoría distingue explícitamente entre lo que el sistema **ya cumple hoy** ("Real",
verificado contra el código) y lo que queda como **objetivo** a alcanzar más adelante — nunca se
mezclan ambas cosas en una sola afirmación.

### RNF-1: Formatos y tamaño de video

- **Real:** extensiones permitidas `.mp4` y `.mov`
  (`backend/app/services/validation.py::ALLOWED_EXTENSIONS`); códec de video exigido: H.264
  (`ALLOWED_VIDEO_CODECS`, mismo archivo); tamaño máximo 100 MB (`104_857_600` bytes,
  `backend/app/config.py`); duración máxima 60s (`backend/app/config.py`). cv-service aplica de
  forma independiente sus propios límites de tamaño y duración
  (`cv-service/main.py::MAX_FILE_SIZE_BYTES`, `MAX_DURATION_SEC`) y rechaza el archivo si no
  puede decodificarlo, pero no tiene lista blanca de extensiones ni comprobación de códec — solo
  el backend exige explícitamente `.mp4`/`.mov` y H.264.
- **Objetivo:** — ya cumplido en ambos servicios; no queda pendiente.

### RNF-2: Latencia de análisis

- **Real:** el análisis es asíncrono (subida → cv-service → webhook → actualización de estado),
  con un reconciliador de respaldo que consulta el estado directamente a cv-service si el webhook
  no llega dentro de un plazo configurado
  (`backend/app/services/jobs.py::reconcile_stale_attempts`, usa `settings.cv_poll_after_sec`).
  Medido el 15 de agosto de 2026 con `cv-service/scripts/benchmark_latencia.py` (subida real por
  HTTP, polling hasta `completed`), sobre `backend/tests/fixtures/squat.mp4` (único video de
  referencia del repo, ~13s), en la máquina de desarrollo (16 núcleos físicos / 22 lógicos): 3
  tandas secuenciales dieron una latencia media de 12.4s (mín. 12.3s, máx. 12.4s) — una relación
  de ~0.95x la duración del video, dominada por el procesamiento frame a frame de MediaPipe, no
  por la subida del archivo en sí.
- **Objetivo:** extrapolando esa relación linealmente a un video de 60s (el máximo del contrato):
  ~57s de procesamiento puro. Se propone un SLA de **menos de 90s** para un video de 60s, dejando
  margen sobre la extrapolación porque la medición es de esta máquina de desarrollo, no del
  destino de despliegue real (`docs/superpowers/specs/2026-08-14-free-tier-deployment-design.md`:
  una VM Oracle Cloud Always-Free de 2 OCPUs ARM, compartida con backend y Postgres) — a
  re-medir con `benchmark_latencia.py` una vez desplegado ahí, ya que una VM mucho más modesta y
  compartida probablemente no sostenga la misma relación de ~1x.

### RNF-3: Capacidad concurrente

- **Real:** el análisis se lanza como `BackgroundTask` de FastAPI dentro del propio proceso de
  cv-service (`cv-service/main.py`), sin cola de trabajos ni workers dedicados, y el estado de
  los jobs vive en un diccionario en memoria (`cv-service/jobs.py::JOBS`) — sin límite explícito
  de análisis en paralelo. Medido el 15 de agosto de 2026 con `benchmark_latencia.py` (mismo
  video, niveles de concurrencia 1/2/3/4, 3 tandas cada uno) en la máquina de desarrollo: la
  latencia por job se mantuvo prácticamente plana hasta concurrencia=4 (1.00x-1.06x contra la
  línea base de concurrencia=1, máx. 14.9s en una tanda) — MediaPipe/OpenCV liberan el GIL lo
  suficiente durante el cómputo pesado como para que los hilos del `BackgroundTask` corran en
  paralelo de verdad, no en serie.
- **Objetivo:** este resultado no es trasladable tal cual al destino de despliegue: 16 núcleos
  de la máquina de desarrollo vs. 2 OCPUs compartidos con backend y Postgres en la VM Oracle
  Always-Free planeada. Con esa referencia (2 OCPUs), se propone **2 análisis simultáneos** como
  objetivo conservador de partida, no como límite medido — pendiente de confirmar re-corriendo
  `benchmark_latencia.py` contra la VM real (o un contenedor con `docker run --cpus 2`, que no se
  probó en esta ronda por no tener Docker Desktop activo en la máquina de desarrollo).

### RNF-4: Precisión del modelo

- **Real:** no es un modelo de ML entrenado con métricas de accuracy/precision/recall — es un
  pipeline de reglas basado en umbrales de ángulo articular (p. ej. `GOOD_DEPTH_MIN` en
  `cv-service/pipeline.py`).
- **Objetivo:** en vez de un target de accuracy clásico, definir un objetivo de fiabilidad de
  detección (p. ej. porcentaje de repeticiones correctamente contadas sobre un set de videos de
  referencia).

### RNF-5: Seguridad

- **Real:** autenticación JWT (access token en memoria, refresh token opaco almacenado sin hashear
  en `localStorage` del cliente pero hasheado con SHA-256 en la base de datos del backend vía
  `hash_refresh_token`, `backend/app/services/auth.py`), revocación en bloque de todos los
  refresh tokens de un usuario ante detección de reuso, firma y verificación HMAC-SHA256 en los
  webhooks entre backend y cv-service (`sign_payload`/`verify_signature`,
  `backend/app/security/signing.py`), y una API key compartida (`X-API-Key`) que cv-service exige
  en cada llamada del backend (`_require_api_key`, `cv-service/security.py`) — la misma clave que
  el proxy de video de CU-5 mantiene fuera del navegador.
- **Objetivo:** — ya cumplido; se documenta como logrado, no como pendiente.

### RNF-6: Disponibilidad

- **Real:** sin despliegue en AWS todavía (solo entorno local/desarrollo); sin SLA de
  disponibilidad definido.
- **Objetivo:** definir un objetivo de disponibilidad (p. ej. 99%) una vez desplegado en
  producción.

### RNF-7: Accesibilidad (WCAG)

- **Real:** no se ha realizado una auditoría formal de accesibilidad; el frontend usa componentes
  de shadcn/ui (basados en Base UI, accesibles por defecto), pero esto no se ha verificado
  explícitamente contra WCAG en este proyecto.
- **Objetivo:** alcanzar conformidad WCAG 2.1 nivel AA, a confirmar con una auditoría (p. ej.
  Lighthouse o axe).
