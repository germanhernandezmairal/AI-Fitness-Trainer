# Diseño: Servicio de evaluación de ejercicios por Computer Vision

**Fecha:** 2026-07-27
**Autor:** Alejandro (parte de Computer Vision / Ciencia de Datos)
**Audiencia:** compañero de backend/frontend

**Revisión 2026-08-04:** §4 actualizada para ratificar el contrato acordado con backend
(`docs/superpowers/specs/2026-07-27-api-contract-design.md` en `main`, implementado como
referencia ejecutable en `fake-cv-service/`): prefijo `/v1`, `DELETE /v1/jobs/{id}` (borrado
GDPR), autenticación (`X-API-Key` + webhook firmado HMAC-SHA256) y límites de subida
confirmados. Segunda ronda (mismo día, tras revisión de seguridad de Germán): `job_id`
obligatorio en el cuerpo del webhook (liga la firma al job y evita reenvío cruzado entre
intentos), validación por contenedor/códec real en vez de `Content-Type`, y soporte de HEVC
pendiente de confirmar en el entorno de despliegue. El resto del diseño original no cambia.

**Revisión 2026-08-04 (verificación end-to-end real):** implementado el MVP del servicio real
(`cv-service/`, ver `docs/superpowers/specs/2026-08-04-cv-service-mvp-design.md`) y probado
sustituyendo a `fake-cv-service` en el entorno local de backend completo (Postgres +
`cv-service` en Docker + backend real): subida → job → análisis con MediaPipe → webhook
firmado → resultado en `GET /v1/attempts/{id}` → video anotado descargable → borrado GDPR
cruzado (`DELETE` en backend → `DELETE` en `cv-service`, confirmado en ambos lados). Todo
correcto. Un hallazgo pendiente de decidir con backend:

- **`annotated_video_url` no es accesible por el usuario final.** Por contrato (§5), este campo
  se pasa tal cual desde `cv-service`, a través del backend, hasta el frontend/usuario — se
  espera que el cliente lo abra directamente. Pero hoy esa ruta exige el mismo `X-API-Key` que
  protege el resto de la API interna backend↔CV, y esa clave es un secreto de servicio que
  nunca debería llegar a un navegador ni a un frontend. Falta decidir cómo se sirve el video al
  usuario final: una URL firmada con caducidad (sin secreto compartido), o que el backend haga
  de proxy de los bytes del video (consistente con "el frontend nunca ve el servicio CV" de
  §1). No es una decisión que `cv-service` pueda tomar solo — afecta a los dos lados.

## 1. Objetivo

Analizar videos de ejercicios de gym (pregrabados, subidos por el usuario) y devolver una
evaluación de qué tan bien se ejecutó el ejercicio: score, feedback por repetición y un video
anotado con el esqueleto/ángulos dibujados.

**Alcance de la primera versión (MVP):** solo sentadilla (squat). El diseño está preparado para
añadir más ejercicios sin cambios estructurales.

**Tipo de algoritmo:** híbrido. Ahora mismo son reglas geométricas (umbrales de ángulos
articulares, como en el prototipo `script.py`), pero el pipeline está diseñado para poder
sustituir esas reglas por un modelo entrenado (ML) más adelante sin cambiar el contrato de API
ni el resto del sistema.

## 2. Arquitectura

El servicio de CV es **independiente** del backend principal de la app (microservicio propio,
con su propia API y despliegue). El backend sube el video, recibe un `job_id` de inmediato, y
consulta el resultado después (procesamiento asíncrono) — evita timeouts en videos largos y
desacopla los ciclos de release de cada equipo.

```
[App móvil/web] --sube video--> [API (FastAPI)] --encola job--> [Cola/Broker] --> [Worker CV]
                                       |                                              |
                                       |<---- job_id inmediato ------------------------|
                                       |                                              |
                                       |                                    [Pipeline CV]
                                       |                                              |
                        [Storage: video anotado + report.json] <---------------------|
                                       |
[App] <--poll/webhook-- [API: GET /v1/jobs/{id}] --> {status, score, report, video_url}
```

### Componentes

1. **API (FastAPI)** — capa fina, sin lógica de CV. Recibe el video, valida (formato, tamaño,
   tipo de ejercicio, `X-API-Key`), lo guarda, crea el job y responde con `job_id`. Expone
   `GET /v1/jobs/{id}` y `DELETE /v1/jobs/{id}`.
2. **Cola de tareas** (Celery + Redis, o RQ) — desacopla la subida del procesamiento pesado.
3. **Worker** — ejecuta el pipeline de CV sobre el video y deja el resultado listo.
4. **Pipeline de CV** (la lógica central, aislada y testeable, sin dependencias de FastAPI/Celery):
   - **Pose extractor**: envuelve MediaPipe, convierte el video en una secuencia de landmarks
     por frame.
   - **Rep segmentation**: máquina de estados que detecta inicio/fin de cada repetición a
     partir de la señal de ángulo (de pie → bajando → abajo → subiendo).
   - **Exercise evaluator** (interfaz `ExerciseEvaluator`, una implementación por ejercicio,
     ej. `SquatEvaluator`): recibe los frames de una repetición y devuelve score + errores
     detectados.
   - **Annotator**: dibuja esqueleto/ángulos/feedback en cada frame y escribe el video de
     salida.
   - **Report builder**: agrega todo en el JSON final.
5. **Storage** — video original, video anotado y report en almacenamiento de objetos (S3 o
   equivalente; MinIO en local). La API solo maneja URLs, nunca sirve binarios directamente.

## 3. Estructura de carpetas

```
ai_fitness/
├── app/
│   ├── api/                      # Capa HTTP — lo único que backend necesita "ver"
│   │   ├── main.py
│   │   ├── routes/jobs.py        # POST /v1/jobs, GET /v1/jobs/{id}, DELETE /v1/jobs/{id}
│   │   └── schemas.py            # Pydantic: request/response (el contrato)
│   ├── worker/
│   │   ├── celery_app.py
│   │   └── tasks.py              # tarea que ejecuta el pipeline completo
│   ├── core/
│   │   ├── config.py             # settings (env vars)
│   │   └── storage.py            # cliente S3/MinIO
│   ├── pipeline/                 # el "modelo" de CV, aislado y testeable
│   │   ├── pose_extractor.py
│   │   ├── rep_segmentation.py
│   │   ├── exercises/
│   │   │   ├── base.py           # interfaz ExerciseEvaluator
│   │   │   ├── squat.py
│   │   │   └── registry.py       # exercise_type -> clase evaluadora
│   │   ├── annotator.py
│   │   └── report.py
│   └── models/                   # modelo de datos del Job (estado, urls, timestamps)
├── configs/
│   └── squat.yaml                # umbrales/parámetros ajustables sin tocar código
├── tests/
│   ├── unit/
│   └── fixtures/                 # videos de prueba cortos + resultados esperados
├── notebooks/                    # exploración/prototipos (NO producción)
├── docs/
│   └── api_contract.md           # contrato para el equipo de backend
├── Dockerfile
├── docker-compose.yml            # API + worker + redis + minio para dev local
└── pyproject.toml
```

## 4. Contrato de API

**Prefijo de versión:** todos los endpoints van bajo `/v1` (ratificado con backend en
`api-contract-design.md` §4 — mantiene consistencia con el resto del sistema y permite romper
compatibilidad en `/v2` sin tocar clientes existentes).

**Autenticación:** cada request de backend → CV service incluye un header `X-API-Key` con un
secreto compartido (`CV_API_KEY`). Una key ausente o incorrecta devuelve `401`. El webhook de
vuelta (CV → backend, ver más abajo) va firmado, no autenticado por API key.

### `POST /v1/jobs` — sube el video y crea el job

```
Content-Type: multipart/form-data
Headers: X-API-Key: <CV_API_KEY>
Campos: video (file), exercise_type (string, ej. "squat"), callback_url (opcional)

Respuesta 202 Accepted:
{
  "job_id": "abc123",
  "status": "queued"
}

Respuesta 401 Unauthorized: X-API-Key ausente o incorrecta.
```

**Límites de subida** (validados aquí, antes de encolar el job — 400 si no se cumplen):
- **Formatos:** contenedor MP4 o MOV, códec de video **H.264 únicamente**. El audio no se
  valida (la estimación de pose no lo usa; exigir AAC rechazaría clips mudos sin motivo).
  **HEVC pendiente de validar**: los `.mov` grabados con iPhone son HEVC por defecto y hoy se
  rechazan como `unsupported_format` — falta confirmar si el pipeline lo decodifica en el
  entorno de despliegue (no solo en local) antes de anunciarlo como soportado.
- **Detección real del formato, no `Content-Type`**: el backend deriva el `Content-Type` del
  multipart a partir del nombre de archivo (un `.mov` llega como `video/quicktime`, no
  `video/mp4`), así que no es fiable para decidir nada. El pipeline debe **inspeccionar el
  contenedor/códec real** del archivo recibido (p. ej. vía `ffprobe` o el propio
  `cv2.VideoCapture`) antes de aceptar o rechazar el job.
- **Tamaño máximo:** 100 MB.
- **Duración máxima:** 60 segundos.
- **Retención:** los artefactos (video original recibido, video anotado, landmarks) se purgan
  a los 30 días de creados (ver `DELETE /v1/jobs/{id}` para borrado explícito antes de ese plazo).

### `GET /v1/jobs/{job_id}` — consulta estado/resultado

```
Headers: X-API-Key: <CV_API_KEY>
```

```json
{
  "job_id": "abc123",
  "status": "completed",
  "created_at": "2026-07-27T18:00:00Z",
  "completed_at": "2026-07-27T18:00:12Z",
  "result": {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Buena profundidad general, pero rodillas colapsan hacia adentro en 2 de 5 repeticiones.",
    "rep_count": 5,
    "reps": [
      {
        "rep_index": 1,
        "start_time_sec": 2.1,
        "end_time_sec": 5.4,
        "min_knee_angle_deg": 78,
        "score": 90,
        "errors": []
      },
      {
        "rep_index": 2,
        "start_time_sec": 6.0,
        "end_time_sec": 9.1,
        "min_knee_angle_deg": 65,
        "score": 60,
        "errors": ["knee_valgus", "insufficient_depth"]
      }
    ],
    "annotated_video_url": "https://storage.../abc123/annotated.mp4",
    "algorithm_version": "squat-rules-v1"
  }
}
```

`status` es uno de: `queued`, `processing`, `completed`, `failed`.

Los `errors` son un **catálogo cerrado de códigos** (`knee_valgus`, `insufficient_depth`,
`excessive_forward_lean`, ...), no texto libre — así el frontend controla textos/traducciones/
iconos sin depender de redacción libre del lado de CV.

### `DELETE /v1/jobs/{job_id}` — borrado del job y sus artefactos

Requisito de backend para completar el borrado de intentos por parte del usuario (GDPR, spec
§7): al recibir `DELETE /v1/attempts/{id}` en su lado, el backend llama a este endpoint para
borrar el video anotado y los landmarks retenidos de ese job.

```
Headers: X-API-Key: <CV_API_KEY>

Respuesta 204 No Content — también si el job ya no existe o ya fue borrado (idempotente:
borrar dos veces, o borrar un job inexistente, nunca debe devolver error).
```

### Webhook (`callback_url`)

Si se envía `callback_url` en `POST /v1/jobs`, al terminar el worker hace `POST` a esa URL con
el mismo payload que `GET /v1/jobs/{id}` — **incluyendo `job_id` en el nivel superior del
cuerpo**, no solo en la URL de callback. Sin esto, la firma HMAC (ver abajo) cubre
`timestamp + body` pero nada liga ese cuerpo firmado al intento concreto: quien capture un
callback válido podría reenviarlo a la URL de otro intento dentro de la ventana de tolerancia
del timestamp, y el backend no tendría forma de detectarlo. Al llevar `job_id` en el cuerpo, el
backend valida que coincide con el job que registró para ese intento y el reenvío cruzado deja
de funcionar. Es un campo aditivo — no rompe al backend si se despliega antes o después de que
él active la comprobación. El polling queda como respaldo si el webhook falla.

El callback va firmado para que el backend pueda verificar que viene realmente de este
servicio:

```
Headers:
  X-CV-Signature: HMAC-SHA256(timestamp + "." + body, CV_WEBHOOK_SECRET), en hex
  X-CV-Timestamp: unix timestamp de envío (el backend rechaza firmas demasiado viejas, anti-replay)
```

`CV_API_KEY` y `CV_WEBHOOK_SECRET` son secretos compartidos con backend, gestionados como env
vars (nunca hardcodeados ni en el repo).

## 5. Manejo de errores

- **Autenticación (401)**: `X-API-Key` ausente o incorrecta, en cualquier endpoint. No se crea
  ni se toca ningún job.
- **Validación en la subida (400)**: formato no soportado (fuera de MP4/MOV), video > 100 MB,
  duración > 60s, `exercise_type` inexistente. Falla inmediata, sin encolar job.
- **`status: failed`**, distinguiendo dos causas:
  - *Error de contenido* (el usuario debe regrabar): no se detectó a la persona, confianza de
    pose demasiado baja, video sin movimiento. No se reintenta.
  - *Error de sistema* (reintentable): fallo al guardar en storage, worker caído. Reintentos
    con backoff.
- Formato del error, mismo patrón de código cerrado que los errores de ejercicio:
  ```json
  { "status": "failed", "error": { "code": "no_pose_detected", "message": "..." } }
  ```

## 6. Testing

- **Unitarios puros**: `calculate_angle`, máquina de estados de `rep_segmentation` (secuencias
  sintéticas de ángulos, sin video), `SquatEvaluator.score()`.
- **Fixtures etiquetadas**: 2-3 videos cortos (`tests/fixtures/`) — sentadilla buena, poca
  profundidad, valgo de rodilla — con resultado esperado.
- **Integración end-to-end**: pipeline completo sobre un fixture, verificando rep_count y rango
  de score (con tolerancia).
- **API**: `TestClient` de FastAPI con el worker en modo síncrono/eager (sin depender de Redis
  en CI). Incluye: rechazo con `401` sin `X-API-Key`/con key incorrecta, firma HMAC del webhook
  (`X-CV-Signature`/`X-CV-Timestamp`), y `DELETE /v1/jobs/{id}` idempotente (job existente, ya
  borrado, e inexistente — los tres devuelven `204`).

## 7. Extensibilidad

- **Nuevo ejercicio**: crear `exercises/<nombre>.py` implementando `ExerciseEvaluator`,
  registrar en `registry.py`, añadir `configs/<nombre>.yaml`. Sin cambios en API, worker ni
  annotator.
- **Swap a modelo ML**: como `ExerciseEvaluator` solo recibe la secuencia de landmarks de un rep
  y devuelve `{score, errors}`, más adelante se puede reemplazar la implementación interna
  (reglas → clasificador entrenado) sin tocar el contrato de API ni el resto del pipeline.
- El campo `algorithm_version` en el report permite comparar resultados de forma consistente
  cuando cambie el algoritmo interno.
