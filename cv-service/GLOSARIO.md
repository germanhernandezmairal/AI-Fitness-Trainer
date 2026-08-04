# Glosario — Servicio CV

Explicación en lenguaje llano de cada concepto y variable que aparece en el código, archivo por
archivo. Se amplía a medida que se añade cada script del plan
(`docs/superpowers/plans/2026-08-04-cv-service-mvp.md`).

## `security.py`

| Nombre | Qué es |
|---|---|
| `API_KEY` | La "contraseña" que debe traer cada petición del backend en el header `X-API-Key` para demostrar que es Germán quien llama, no cualquiera. Se lee de la variable de entorno `CV_API_KEY`; si no está definida, usa un valor de prueba (`dev-cv-api-key`) solo para desarrollo local. |
| `WEBHOOK_SECRET` | Una segunda contraseña, distinta de `API_KEY`, que solo tú y el backend conocéis. Se usa para *firmar* (no para autenticar) el webhook que le mandas a Germán cuando termina el análisis — así él puede comprobar que el mensaje viene de verdad de tu servicio y no de un tercero. Se lee de `CV_WEBHOOK_SECRET`. |
| `check_api_key(provided)` | Función que compara la clave recibida contra `API_KEY`. Devuelve `True`/`False`. |
| `sign_webhook(body, timestamp)` | Función que calcula la firma del webhook. |
| **HMAC-SHA256** | Un algoritmo criptográfico que, a partir de un mensaje (`body`) y una clave secreta (`WEBHOOK_SECRET`), genera una "huella" (la firma) que es prácticamente imposible de falsificar sin conocer la clave. El backend recalcula la misma huella con su copia del secreto y compara: si coinciden, el mensaje es auténtico. |
| `timestamp` | La hora (en segundos desde 1970, "Unix time") en la que se firma el webhook. Se incluye en lo que se firma para que, si alguien captura un mensaje válido y lo reenvía más tarde ("replay attack"), el backend pueda rechazarlo por tener una marca de tiempo demasiado antigua. |
| `body` | El contenido (en bytes) del mensaje que se está firmando — el JSON con el resultado del análisis, ya convertido a texto. |

## `pipeline.py` (funciones puras — Task 2, sin video real todavía)

| Nombre | Qué es |
|---|---|
| `STANDING_THRESHOLD` (160°) | Ángulo de rodilla a partir del cual consideramos que la persona está "de pie". Por debajo de ese ángulo, está en movimiento de sentadilla. |
| `GOOD_DEPTH_MIN` / `GOOD_DEPTH_MAX` (70°-100°) | El rango de ángulo mínimo que consideramos "buena profundidad" en la parte baja de la sentadilla. |
| `PENALTY_PER_DEGREE` | Cuántos puntos de `score` se restan por cada grado que el ángulo mínimo de una rep se aleja del rango bueno. |
| `NoPoseDetectedError` | Un tipo de error a medida (no lleva lógica propia, solo un nombre) que se lanza cuando MediaPipe no detecta a ninguna persona en todo el video. Sirve para que `jobs.py` distinga este caso ("el usuario debe regrabar") de un fallo inesperado del sistema — ver conversación sobre por qué no es un error genérico. |
| `calculate_angle(a, b, c)` | Calcula el ángulo (en grados) entre tres puntos, con vértice en `b`. Se usa con (cadera, rodilla, tobillo) para obtener el ángulo de la rodilla en cada frame. |
| `score_from_angle(min_angle)` | Convierte el ángulo mínimo alcanzado en una repetición en una puntuación de 0 a 100. |
| `build_rep(...)` | Empaqueta los datos de una repetición (índice, tiempos de inicio/fin, ángulo mínimo, score) en el diccionario con la forma exacta que espera el contrato de API. |
| `segment_reps(detections, fps)` | La "máquina de estados": recorre la lista de ángulos frame a frame y decide dónde empieza y termina cada repetición (de pie → bajando → de pie de nuevo). `detections` es una lista de pares `(número_de_frame, ángulo)`, uno solo por cada frame donde sí se detectó a la persona. |
| `fps` (frames por segundo) | Cuántos frames tiene el video por cada segundo real. Se usa para convertir "número de frame" en "segundos", y así calcular `start_time_sec`/`end_time_sec` de cada rep. |
| `state` | La variable que recuerda en qué parte del movimiento estamos mientras se recorren los frames: `"standing"` (de pie, esperando que empiece una rep) o cualquier otro valor (dentro de una rep, bajando/subiendo). |

## `jobs.py`

| Nombre | Qué es |
|---|---|
| `JOBS` | El "estado" del servicio: un diccionario en memoria que va de `job_id` al último payload conocido de ese job (`queued`, `processing`, `completed` o `failed`, con su resultado o error). Vive mientras el proceso está corriendo; si reinicias el servidor, se vacía — el backend hace polling de respaldo por si acaso. |
| `STORAGE_DIR` | La carpeta (`cv-service/storage/`) donde se guardan, uno por `job_id`, el video que sube el backend y el video anotado que genera `pipeline.py`. |
| `BASE_URL` | El prefijo (`http://localhost:8000` por defecto) con el que se construye la URL pública del video anotado (`annotated_video_url`) que se manda de vuelta al backend. |
| `job_id` | El identificador único de un análisis concreto, generado por `new_job_id()`. Es la clave que conecta todo: la carpeta en disco, la entrada en `JOBS`, y (desde ahora) el campo `job_id` dentro del propio resultado, para que la firma del webhook quede atada a ese job en concreto (el problema de seguridad que señaló Germán). |
| `callback_url` | La URL que el backend nos da al crear el job, para que le avisemos por webhook cuando termine el análisis. Es opcional: si no viene, el backend simplemente hace polling con `GET /v1/jobs/{id}` hasta ver el resultado. |
| **BackgroundTask** | Un mecanismo de FastAPI (lo usaremos en `main.py`, Task 5) para decirle "ejecuta esta función *después* de responder al cliente". Así `POST /v1/jobs` puede devolver `202 Accepted` al instante, mientras `run_job` sigue analizando el video en segundo plano. |
| **monkeypatch** (en los tests) | Una fixture de pytest que te deja sustituir temporalmente una función o variable por otra (por ejemplo, `pipeline.analizar_video` por una versión falsa que no procesa video de verdad) solo durante ese test — al terminar, todo vuelve a la normalidad. Así probamos `run_job` sin esperar a que MediaPipe analice un video real. |

## `main.py`

### Sintaxis de FastAPI, pieza por pieza

| Sintaxis | Qué es |
|---|---|
| `app = FastAPI(...)` | El objeto que representa "el servidor web". Todo lo demás se cuelga de `app`. |
| `@app.post("/v1/jobs")` | Un **decorador**: la línea justo encima de una función, con `@`, que le dice a FastAPI "cuando llegue un `POST` a esta URL, ejecuta la función de abajo". No es magia, es Python normal — el decorador envuelve la función y la registra en `app`. Hay uno por cada combinación de verbo HTTP (`post`/`get`/`delete`) + URL. |
| `x_api_key: str \| None = Header(default=None)` | Le dice a FastAPI "lee el header `X-API-Key` de la petición y pásamelo como el parámetro `x_api_key`". FastAPI convierte el nombre del parámetro a formato de header automáticamente. `Header(default=None)` significa "si no viene, pásame `None`" en vez de dar error. |
| `exercise_type: str = Form(...)` | Igual que `Header`, pero para leer un campo de un formulario (`multipart/form-data`, que es como se suben archivos). Los `...` (`Ellipsis`) significan "obligatorio, sin valor por defecto". |
| `video: UploadFile = File(...)` | Igual, pero para el archivo subido en sí. `UploadFile` es un objeto de FastAPI con un método `.read()` para leer el contenido en bytes. |
| `async def` / `await` | Marca una función como "puede pausarse mientras espera algo" (aquí, leer el archivo subido). `await video.read()` significa "espera a que termine de leerse el archivo antes de seguir". Las otras rutas (`get_job`, `delete_job`) no tienen `async` porque no esperan nada de este tipo — son funciones normales. |
| `HTTPException(status_code=400, detail={...})` | La forma de decir "corta aquí y responde con un error". FastAPI atrapa esta excepción en cualquier punto de la función y construye la respuesta HTTP con ese código y ese cuerpo — no hace falta un `return` explícito para los casos de error. |
| `BackgroundTasks` / `background_tasks.add_task(fn, *args)` | El mecanismo para decir "ejecuta `fn(*args)` después de responder al cliente, no ahora". Por eso `POST /v1/jobs` puede devolver `202` al instante mientras `jobs.run_job` sigue analizando el video por detrás. |
| `FileResponse(path, media_type=...)` | Le dice a FastAPI "la respuesta de esta ruta es el contenido de este archivo", en vez de un diccionario que se convierte a JSON. Así se sirve el video anotado. |

### Cómo viaja una petición real (ejemplo: `POST /v1/jobs`)

1. El backend de Germán hace un `POST` a `http://tu-servidor:8000/v1/jobs`, con el video adjunto como `multipart/form-data`, el campo `exercise_type=squat`, y el header `X-API-Key: dev-cv-api-key`.
2. Uvicorn (el programa que de verdad escucha el puerto 8000) recibe la conexión y se la pasa a FastAPI.
3. FastAPI mira la URL y el verbo (`POST /v1/jobs`) y encuentra la función `create_job` (por el decorador `@app.post("/v1/jobs")`).
4. Antes de ejecutar tu código, FastAPI **rellena los parámetros** de `create_job` leyendo la petición: el header `X-API-Key` va a `x_api_key`, el campo de formulario `exercise_type` va a `exercise_type`, el archivo va a `video`. Esto es lo que hacen `Header(...)`/`Form(...)`/`File(...)` — son instrucciones para FastAPI, no lógica tuya.
5. Ahora sí, se ejecuta el cuerpo de `create_job`, línea por línea, tal como está escrito: `_require_api_key` → `_validate_exercise_type` → `await video.read()` → `_validate_size` → guardar en disco → `_validate_format_and_duration` → `jobs.create_job` → `background_tasks.add_task(...)`.
6. Si en cualquier paso se lanza `HTTPException`, todo lo que queda por debajo se salta y FastAPI responde inmediatamente con ese código de error.
7. Si todo va bien, la función termina con `return {"job_id": ..., "status": "queued"}` — FastAPI lo convierte a JSON y responde `202 Accepted` **en este momento**.
8. Justo después de responder, FastAPI ejecuta la tarea que se registró con `background_tasks.add_task(jobs.run_job, ...)` — ahí es donde de verdad se analiza el video, ya sin que el backend esté esperando.
9. Cuando `jobs.run_job` termina, si había `callback_url`, se manda el webhook firmado (visto en `jobs.py`). Si no, el backend se entera más tarde llamando a `GET /v1/jobs/{job_id}` — que sigue el mismo recorrido de los pasos 2-4, pero llega a la función `get_job` en vez de `create_job`.

## `scripts/probar_api.py`

No es parte del servicio — es una herramienta para ti, para comprobar que todo lo de arriba
funciona junto de verdad (no solo cada pieza por separado con pytest). Hace exactamente lo que
haría el backend de Germán: sube un video real a tu API con `httpx.post`, y luego pregunta el
estado con `httpx.get` cada 2 segundos (`polling`) hasta que el `status` deja de ser
`"processing"`. Verificado de extremo a extremo: servidor real levantado con `uvicorn`, video
subido, 6 reps detectadas (igual que en la Task 3), video anotado descargable en
`GET /v1/jobs/{id}/video`, y `DELETE /v1/jobs/{id}` confirmado como borrado real (un `GET`
posterior da `404`).

