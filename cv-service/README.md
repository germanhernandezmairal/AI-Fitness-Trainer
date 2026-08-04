# CV Service (MVP)

Servicio de visión por computador que analiza videos de sentadilla y cumple el contrato `/v1`
acordado con backend. Ver `docs/superpowers/specs/2026-08-04-cv-service-mvp-design.md` para el
diseño completo, `docs/2026-07-27-cv-gym-exercise-design.md` para el contrato original, y
`GLOSARIO.md` para una explicación en lenguaje llano de cada concepto y variable del código.

## Instalar

`mediapipe==0.10.14` no tiene wheels para Python 3.13+ (confirmado corriéndolo en macOS/arm64) —
usa un entorno **Python 3.12** propio para este servicio, distinto del que use `backend/` (ese sí
puede ir en una versión más nueva; no comparten venv).

Desde la raíz del repo, con el entorno virtual ya activo:

```bash
.venv/Scripts/python.exe -m pip install -r cv-service/requirements.txt
```

## Arrancar el servidor

```bash
cd cv-service
../.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000
```

## Probar de punta a punta

En otra terminal, con el servidor ya corriendo:

```bash
cd cv-service
../.venv/Scripts/python.exe scripts/probar_api.py
```

Sube `backend/tests/fixtures/squat.mp4` (el video de prueba del repo), hace polling a
`GET /v1/jobs/{id}` cada 2 segundos, e imprime el resultado final. El video anotado queda en
`cv-service/storage/<job_id>/annotated.mp4`.

## Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `CV_API_KEY` | `dev-cv-api-key` | debe coincidir con lo que envíe el backend |
| `CV_WEBHOOK_SECRET` | `dev-webhook-secret-change-me-in-production` | firma HMAC del webhook |
| `CV_SERVICE_BASE_URL` | `http://localhost:8000` | prefijo con el que se construye `annotated_video_url` |

## Correr los tests

```bash
cd cv-service
../.venv/Scripts/python.exe -m pytest -v
```

## Docker

```bash
docker build -t cv-service:local cv-service/
docker run -d --name cv-service-e2e -p 9000:9000 \
  -e CV_API_KEY=dev-cv-api-key \
  -e CV_WEBHOOK_SECRET=dev-webhook-secret-change-me-in-production \
  -e CV_SERVICE_BASE_URL=http://localhost:9000 \
  --add-host=host.docker.internal:host-gateway \
  cv-service:local
```

Puerto 9000 y las mismas variables de entorno de desarrollo que usa `fake-cv-service` — así es
un reemplazo directo suyo en `backend/docker-compose.yml` (`CV_SERVICE_URL=http://localhost:9000`
por defecto en el `.env.example` del backend, sin tocar nada). Verificado de extremo a extremo
contra el backend real (rama `main`): subida → job → webhook firmado → resultado → video
anotado → borrado GDPR cruzado, todo correcto.

Ya integrado en `backend/docker-compose.yml` como servicio `cv-service` (perfil `real-cv`, ver
"En docker-compose" abajo). El hallazgo de la verificación end-to-end (`annotated_video_url`
exigía `X-API-Key` para verse, pero el contrato espera que el usuario final pueda abrirlo
directamente) ya está resuelto del lado del backend: `GET /v1/attempts/{id}/video` hace de proxy
autenticado con JWT, así que este servicio no necesitó ningún cambio.

## En docker-compose

`fake-cv-service` sigue siendo el servicio por defecto (liviano, sin MediaPipe/OpenCV, con
inyección determinista de fallos vía `FAKE_FORCE_FAILURE`) — sigue arrancando con
`docker compose up -d db fake-cv`. Este servicio real vive detrás del perfil `real-cv`, para no
forzar la build de MediaPipe/OpenCV en quien solo necesita el loop del backend:

```bash
docker compose --profile real-cv up -d db cv-service
```

Ambos escuchan en el puerto 9000, así que no deben correr a la vez: cada uno es un reemplazo
completo del otro para `CV_SERVICE_URL`, no un complemento.

## Fuera de alcance en este MVP

Ver la sección "Fuera de alcance" de
`docs/superpowers/specs/2026-08-04-cv-service-mvp-design.md`: sin detección de `knee_valgus` /
`insufficient_depth` / `excessive_forward_lean` todavía, sin cola de tareas ni S3, sin soporte
HEVC confirmado, sin purga automática por retención.
