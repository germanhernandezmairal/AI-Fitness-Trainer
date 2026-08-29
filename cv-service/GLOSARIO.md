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
| `GOOD_DEPTH_ANGLE_DEG` (100°) | Ángulo de rodilla (cadera-rodilla-tobillo) a partir del cual una rep cuenta como "buena profundidad". Por debajo o igual (más flexión, más profunda), la rep no se penaliza ni se marca `insufficient_depth`; por encima (menos flexión, no llegó a agacharse lo suficiente), sí. Antes existían dos límites (`GOOD_DEPTH_MIN`/`GOOD_DEPTH_MAX` = 70°-100°) que penalizaban tanto quedarse corto como pasarse de profundo — ver "Fuentes" abajo para por qué se cambió a un único umbral. |
| `EXCESSIVE_LEAN_DEG` (45°) | Umbral de `torso_lean_from_vertical` a partir del cual se marca `excessive_forward_lean`. A diferencia de `GOOD_DEPTH_ANGLE_DEG`, es un punto de partida heurístico (no viene de la búsqueda bibliográfica de abajo) — a ajustar contra videos reales. |
| `PENALTY_PER_DEGREE` | Cuántos puntos de `score` se restan por cada grado que el ángulo mínimo de una rep supera `GOOD_DEPTH_ANGLE_DEG`. |
| `NoPoseDetectedError` | Un tipo de error a medida (no lleva lógica propia, solo un nombre) que se lanza cuando MediaPipe no detecta a ninguna persona en todo el video. Sirve para que `jobs.py` distinga este caso ("el usuario debe regrabar") de un fallo inesperado del sistema — ver conversación sobre por qué no es un error genérico. |
| `calculate_angle(a, b, c)` | Calcula el ángulo (en grados) entre tres puntos, con vértice en `b`. Se usa con (cadera, rodilla, tobillo) para obtener el ángulo de la rodilla en cada frame, y con (cadera, hombro) más un eje vertical dentro de `torso_lean_from_vertical`. |
| `torso_lean_from_vertical(hip, shoulder)` | Ángulo (solo magnitud, sin dirección) entre el vector cadera→hombro y la vertical de la imagen. 0° = torso erguido. No distingue adelante de atrás por sí sola — ver `is_excessive_forward_lean`. Se evalúa en el frame donde ocurre el ángulo mínimo de rodilla de cada rep (el punto más bajo del squat), no en cualquier frame. |
| `MIN_TORSO_VECTOR_NORM_PX` (1.0) | Norma mínima en píxeles que debe tener el vector cadera→hombro o el vector tobillo→rodilla para confiar en su dirección; por debajo, se trata como ruido de tracking de sub-píxel y no se marca `excessive_forward_lean`. |
| `is_excessive_forward_lean(hip, knee, ankle, shoulder)` | Decide si `excessive_forward_lean` aplica: usa la posición horizontal de la rodilla respecto al tobillo como referencia de "adelante" (independiente de hacia qué lado mire la cámara), y solo marca el error si el hombro se inclina hacia ese mismo lado Y la magnitud de `torso_lean_from_vertical` supera `EXCESSIVE_LEAN_DEG`. Ver "de dónde sale cada código" más abajo para la historia completa. |
| `score_from_angle(min_angle)` | Convierte el ángulo mínimo alcanzado en una repetición en una puntuación de 0 a 100, según `GOOD_DEPTH_ANGLE_DEG`. |
| `build_rep(...)` | Empaqueta los datos de una repetición (índice, tiempos de inicio/fin, ángulo mínimo, score, `errors`) en el diccionario con la forma exacta que espera el contrato de API. Recibe opcionalmente `hip`/`knee`/`ankle`/`shoulder` del frame de ángulo mínimo -- si falta alguno, no evalúa `excessive_forward_lean`. |
| `segment_reps(detections, fps)` | La "máquina de estados": recorre la lista de ángulos frame a frame y decide dónde empieza y termina cada repetición (de pie → bajando → de pie de nuevo), y recuerda los landmarks del frame de ángulo mínimo de cada rep para pasárselos a `build_rep`. `detections` es una lista de `(número_de_frame, ángulo, hip, knee, ankle, shoulder)`, una por cada frame donde sí se detectó a la persona. |
| `fps` (frames por segundo) | Cuántos frames tiene el video por cada segundo real. Se usa para convertir "número de frame" en "segundos", y así calcular `start_time_sec`/`end_time_sec` de cada rep. |
| `state` | La variable que recuerda en qué parte del movimiento estamos mientras se recorren los frames: `"standing"` (de pie, esperando que empiece una rep) o cualquier otro valor (dentro de una rep, bajando/subiendo). |

### `rep.errors` — de dónde sale cada código, y de dónde no

Contrato original (catálogo cerrado, sin lógica): `docs/2026-07-27-cv-gym-exercise-design.md` §7.
Diseño de esta detección: `docs/superpowers/specs/2026-08-07-cv-form-error-detection-request-design.md`
y el mensaje asociado en `docs/2026-08-11-alejandro-cv-form-error-detection-message.md`.

- **`insufficient_depth`** y **la curva de `score_from_angle`** están basadas en:
  - Schoenfeld, B. J. (2010). *Squatting Kinematics and Kinetics and Their Application to
    Exercise Performance*. Journal of Strength and Conditioning Research, 24(12), 3497-3506 —
    clasifica la profundidad de sentadilla por flexión de rodilla (cuarto ~40-50°, paralela
    ~90°, completa 110-130°+) y es la referencia más citada en biomecánica de sentadilla.
  - NSCA, *Considerations for Squat Depth* (nsca.com/education/articles/nsca-coach/considerations-for-squat-depth) —
    posición de la NSCA de que la evidencia científica no sostiene que la sentadilla completa
    exponga la rodilla a fuerzas de compresión dañinas, en contra del mito de que "más profundo
    es más riesgoso".
  - Escamilla, R. F., *Knee Biomechanics of the Dynamic Squat Exercise* — documenta que las
    fuerzas de compresión patelofemoral y tibiofemoral aumentan progresivamente con la flexión
    de rodilla, pero no que eso implique daño en sentadillas bien ejecutadas.

  Con esa base: `score_from_angle` dejó de penalizar pasarse de profundidad (antes penalizaba
  simétricamente, lo que hacía puntuar 7-22/100 un squat real, limpio y de 39-44° — ver
  verificación end-to-end del 2026-08-04 en `docs/superpowers/specs/2026-08-07-cv-form-error-detection-request-design.md`
  §0). `insufficient_depth` y el score comparten ahora un único umbral (`GOOD_DEPTH_ANGLE_DEG`),
  en vez de los dos límites (`GOOD_DEPTH_MIN`/`GOOD_DEPTH_MAX`) que tenía antes.

- **`excessive_forward_lean`** — el umbral (`EXCESSIVE_LEAN_DEG` = 45°) es un punto de partida
  propuesto en el mensaje a Alejandro, sin respaldo bibliográfico específico — a validar contra
  videos de referencia reales, no una cifra de la literatura.

  La primera versión de `torso_lean_from_vertical` solo medía magnitud de inclinación, sin
  distinguir adelante de atrás (un torso 45° hacia atrás daba el mismo ángulo que uno 45° hacia
  adelante) — encontrado en revisión de código el 20 de agosto de 2026, ver
  `docs/2026-08-20-alejandro-cv-form-error-detection-followup-message.md`. `is_excessive_forward_lean`
  arregla esto usando la posición horizontal de la rodilla respecto al tobillo como referencia de
  "adelante" (avanza en esa dirección durante el descenso sin importar hacia qué lado mire la
  cámara), y descarta la medición por completo (`MIN_TORSO_VECTOR_NORM_PX`) cuando cadera/hombro o
  tobillo/rodilla quedan casi coincidentes en píxeles, para no confiar en ruido de tracking de
  sub-píxel.

  **Limitación conocida de esta heurística, no un bug:** asume que más inclinación de torso viene
  acompañada de más avance de rodilla sobre el tobillo, que es lo típico. Pero un squat muy
  hip-dominant/low-bar, o una dorsiflexión de tobillo limitada que impide que la rodilla avance,
  puede producir un torso genuinamente muy inclinado hacia adelante con la rodilla quieta o incluso
  detrás del tobillo -- en ese caso las dos señales no coinciden y no se marca el error, aunque
  visualmente sí haya inclinación excesiva. Al validar `EXCESSIVE_LEAN_DEG` contra videos reales
  (punto pendiente de arriba), conviene incluir a propósito algún video de ese estilo de sentadilla.

- **`knee_valgus`** — **no implementado en esta ronda**, a propósito, no por omisión.
  `pipeline.py` asume una sola cámara lateral (usa solo landmarks del lado derecho:
  `RIGHT_HIP`, `RIGHT_KNEE`, `RIGHT_ANKLE`, `RIGHT_SHOULDER`), y el valgo de rodilla es un
  defecto que se observa en el plano frontal (de frente), no en el sagital (de lado). Detectarlo
  con una sola cámara lateral requeriría el eje Z de MediaPipe, conocido por ser ruidoso con una
  sola cámara — se decidió (con Germán, 2026-08-07) dejarlo documentado como limitación conocida
  en vez de forzar una señal de baja confianza esta ronda. Sigue devolviendo `errors: []` en la
  práctica para este código: nunca se añade, no hay lógica que lo evalúe.

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

