# Design: Servicio CV — implementación MVP

**Fecha:** 2026-08-04
**Autor:** Alejandro (parte de Computer Vision / Ciencia de Datos), compilado con Claude
**Estado:** APROBADO (2026-08-04)
**Relacionado:** `docs/2026-07-27-cv-gym-exercise-design.md` (diseño/contrato original, revisado
2026-08-04), `docs/superpowers/specs/2026-07-27-api-contract-design.md` en `main` (contrato
ratificado por backend), `fake-cv-service/` en `main` (implementación de referencia del
contrato), `script.py` (prototipo de detección de postura).

---

## 0. Contexto y objetivo

`script.py` ya calcula el ángulo de rodilla frame a frame con MediaPipe y lo muestra en una
ventana interactiva (`cv2.imshow`), pero no cumple el contrato acordado con backend: no cuenta
repeticiones, no calcula un score, no detecta errores de forma, no guarda un video anotado en
disco y no expone ninguna API.

El objetivo de este documento es diseñar la primera versión funcional del servicio CV real: una
API que cumpla el contrato `/v1` ya documentado, envolviendo la lógica de `script.py`.

**Restricción explícita de este diseño:** el autor no tiene experiencia previa en backend. Cada
decisión de este documento prioriza simplicidad y número mínimo de conceptos nuevos sobre
fidelidad al diseño de producción original (que preveía Celery + Redis + S3/MinIO). Migrar a esa
arquitectura queda como trabajo futuro explícito si hace falta escalar, no como parte de este MVP.

## 1. Arquitectura

Un único proceso FastAPI, sin cola de tareas ni almacenamiento externo:

```
Backend --POST /v1/jobs (video + X-API-Key)--> [FastAPI: servicio CV]
                                                        |
                                          guarda video en storage/<job_id>/input.mp4
                                          responde 202 {job_id, status: queued}
                                                        |
                                          BackgroundTask (mismo proceso, sin Redis)
                                                        |
                                          pipeline.analizar_video(path)
                                                        |
                                    actualiza el estado del job (dict en memoria)
                                                        |
                                  si hay callback_url --> POST firmado (HMAC) al backend
                                  si no, el backend hace GET /v1/jobs/{id} (polling)
```

El video anotado se sirve desde el propio servicio (`GET /v1/jobs/{id}/video`) en vez de subirlo
a almacenamiento de objetos — evita añadir un cliente S3/MinIO para el MVP.

## 2. Componentes

- **`main.py`** — la API: `POST /v1/jobs`, `GET /v1/jobs/{id}`, `DELETE /v1/jobs/{id}`, y la
  ruta que sirve el video anotado. Capa fina: valida, delega, responde.
- **`pipeline.py`** — la lógica de `script.py` adaptada: procesa el video completo (no
  interactivo) y devuelve un diccionario con el resultado. Añade sobre el prototipo:
  - Una máquina de estados simple (de pie → bajando → abajo → subiendo) para detectar el
    inicio/fin de cada repetición a partir de la señal de ángulo.
  - `min_knee_angle_deg` y un score básico por rep, derivados del ángulo mínimo alcanzado,
    reutilizando los umbrales que ya usa `script.py` (70°–100° = profundidad buena): `score =
    100` si `min_knee_angle_deg` cae en `[70, 100]`; fuera de ese rango, penaliza
    proporcionalmente a la distancia al límite más cercano hasta un mínimo de `0` (p. ej. a 10°
    de distancia del rango, `score = 100 - 10*penalización_por_grado`, con la pendiente exacta
    a afinar en la implementación). `overall_score` del job es la media de los scores de sus
    reps.
  - Reescritura del dibujo de esqueleto/ángulo existente a un archivo de video
    (`cv2.VideoWriter`) en vez de a pantalla.
- **`security.py`** — comprobar `X-API-Key`; firmar el webhook con HMAC-SHA256 sobre
  `timestamp + "." + body`, igual que `fake-cv-service/main.py` (compatibilidad byte a byte).
- **`jobs.py`** — el diccionario en memoria (`JOBS: dict[str, dict]`) y la función que orquesta
  el análisis en segundo plano y dispara el webhook si corresponde.
- **`storage/`** — carpeta local (en `.gitignore`) con los videos subidos y anotados, uno por
  `job_id`.

## 3. Flujo de datos

### `POST /v1/jobs`
1. `X-API-Key` ausente o incorrecta → `401` inmediato, no se crea nada.
2. Valida tamaño (≤100MB) e intenta abrir el video con OpenCV como comprobación real de
   contenedor/códec (no se confía en `Content-Type`, según lo acordado con Germán) → `400
   unsupported_format` / `400 file_too_large` si falla, sin crear job.
3. Valida duración ≤60s vía `frame_count / fps` → `400 video_too_long` si se excede.
4. Genera `job_id`, guarda el video en `storage/<job_id>/input.mp4`, registra el job como
   `queued`.
5. Lanza el análisis como `BackgroundTask` y responde `202 {job_id, status: queued}`
   inmediatamente.

### Tarea en segundo plano
1. Marca el job como `processing`.
2. Llama a `pipeline.analizar_video(path)`.
3. Si no se detecta a la persona en ningún frame → `status: failed`, `error.code:
   no_pose_detected` (no reintentable).
4. Excepción inesperada durante el análisis → `status: failed`, `error.code: worker_error`,
   capturada con try/except (la tarea de fondo nunca debe tumbar el proceso).
5. Si todo va bien → `status: completed`, con `errors: []` en cada rep por ahora — la detección
   de `knee_valgus` / `insufficient_depth` / `excessive_forward_lean` se añade en una iteración
   posterior sin tocar el contrato (ver `docs/2026-07-27-cv-gym-exercise-design.md` §7,
   Extensibilidad).
6. Guarda el resultado en `JOBS[job_id]`, incluyendo `job_id` en el nivel superior del payload
   (requisito añadido por Germán para atar la firma HMAC al job y evitar reenvío cruzado entre
   intentos).
7. Si había `callback_url`: firma el payload y hace `POST` con `X-CV-Signature` /
   `X-CV-Timestamp`. Si ese `POST` falla, no se reintenta — el polling del backend es el
   respaldo.

### `GET /v1/jobs/{id}`
Comprueba `X-API-Key`. Devuelve el estado actual de `JOBS[job_id]` (mismo payload que el
webhook). `404` si el `job_id` no existe.

### `DELETE /v1/jobs/{id}`
Comprueba `X-API-Key`. Borra `storage/<job_id>/` si existe y quita la entrada del diccionario.
Siempre `204`, exista o no el job (idempotente — requisito GDPR del contrato).

## 4. Manejo de errores

| Situación | Respuesta |
|---|---|
| `X-API-Key` ausente/incorrecta (cualquier endpoint) | `401`, no crea/modifica nada |
| Formato no soportado o códec no decodificable | `400 unsupported_format` |
| Video > 100MB | `400 file_too_large` |
| Video > 60s | `400 video_too_long` |
| `exercise_type` desconocido | `400 unknown_exercise_type` |
| No se detecta a la persona en el video | `status: failed`, `error.code: no_pose_detected` |
| Fallo inesperado durante el análisis | `status: failed`, `error.code: worker_error` |
| `GET` de un `job_id` inexistente | `404` |
| `DELETE` de un `job_id` inexistente o ya borrado | `204` |

## 5. Testing

**Manual, para aprender la forma del código:**
- `scripts/probar_api.py` (o instrucciones `curl` en el README): sube `squat.mp4` a
  `POST /v1/jobs`, guarda el `job_id`, hace `GET /v1/jobs/{id}` en bucle hasta `completed`.
- Revisión visual del `annotated.mp4` generado y del JSON de resultado.

**Automatizado, solo donde un fallo sería difícil de detectar a simple vista** (una vez que la
forma general esté estable):
- `security.py`: la firma HMAC generada coincide con lo que verificaría el backend.
- Validación de límites: `400` para archivo demasiado grande / formato no soportado.
- `DELETE` idempotente: doble borrado y borrado de `job_id` inexistente devuelven `204`.

No hay tests de la parte puramente visual (dibujo del esqueleto) — se revisa a ojo.

## 6. Fuera de alcance (explícitamente diferido)

- Detección de errores de forma (`knee_valgus`, `insufficient_depth`, `excessive_forward_lean`)
  — `errors: []` por ahora.
- Cola de tareas (Celery/Redis) y almacenamiento de objetos (S3/MinIO) — el diccionario en
  memoria y el disco local bastan mientras el servicio corre en una sola máquina para pruebas
  locales.
- Soporte de HEVC (`.mov` de iPhone) — pendiente de validar en el entorno de despliegue real
  (ver `docs/2026-07-27-cv-gym-exercise-design.md`, Revisión 2026-08-04).
- Purga automática a los 30 días (retención) — el `DELETE` explícito ya es idempotente y
  cumple GDPR bajo demanda; la purga por TTL es trabajo de infraestructura posterior.
- Despliegue fuera de la máquina local del autor — conectar con el backend real de Germán es un
  paso posterior a validar este servicio de forma aislada.
