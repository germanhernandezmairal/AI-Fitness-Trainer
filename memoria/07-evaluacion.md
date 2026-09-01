<!--
Fuente: docs/superpowers/specs/2026-09-01-memoria-cap7-evaluacion-design.md (diseño aprobado).
Capítulo retrospectivo: documenta la evaluación realmente hecha (suites automatizadas, dos pruebas
extremo a extremo, pruebas manuales del pipeline sobre vídeo real, y el benchmark del 15/08/2026),
trazada a los requisitos del capítulo 4. Recuentos de pruebas verificados ejecutando las suites el
01/09/2026. Números de latencia/concurrencia citados de §4 (RNF-2/RNF-3), no recalculados aquí.
-->

# 7. Evaluación

## 7.1 Estrategia de evaluación

El sistema tiene **dos objetos de evaluación de naturaleza distinta**.

El **primero es la aplicación web**. Su comportamiento está definido por los requisitos del
capítulo 4 (CU-1…CU-7 y RNF-1…RNF-7), así que se evalúa **verificándola contra esos requisitos**:
pruebas automatizadas por componente, dos pruebas extremo a extremo y comprobaciones manuales a
través de la interfaz en ejecución.

El **segundo es el pipeline de análisis de movimiento** (§6.1). Es un sistema de **reglas
deterministas** sobre un detector de pose pre-entrenado, no un clasificador entrenado: no hay
conjunto de entrenamiento, no hay conjunto de vídeos etiquetados y no aplica una cifra de
*accuracy* / *precision* / *recall* (§6.1.6, §4 RNF-4). Se evalúa **observando su comportamiento
sobre vídeo de sentadilla real** y registrando dónde acierta y dónde falla (§7.5).

**Metodología.** Cada funcionalidad y cada capítulo de esta memoria se construyó siguiendo un flujo
de trabajo dirigido por pruebas (*test-first*); el capítulo 3 lo narra por fases y el historial de
Git muestra los *commits* de pruebas acompañando o precediendo a los de implementación. Las suites
automatizadas son el producto duradero de ese proceso, no un añadido posterior.

**Lo que deliberadamente no se hizo, y por qué es defendible en este TFG:**

- **No se construyó un conjunto de vídeos etiquetados** para validar el pipeline de visión.
  Construir y etiquetar ese conjunto es un proyecto en sí mismo, fuera del alcance de un TFG de dos
  personas con un MVP congelado. La consecuencia —que el objetivo de fiabilidad de RNF-4 queda sin
  cuantificar— se asume abiertamente en §7.6.
- **No hubo una campaña de pruebas formal** más allá de las suites que se entregaron con cada
  funcionalidad: el MVP está congelado, no hay código nuevo contra el que hacer campaña.
- **La evaluación del pipeline (§7.5) es exploratoria**, no sistemática: unos pocos vídeos, sin
  etiquetas de verdad-terreno.

## 7.2 Pruebas automatizadas

Desglose por componente. Cada recuento se enuncia *a fecha de `d14bd8c`* para que sea falsable: las
tres suites se ejecutaron el 01/09/2026 con este resultado —backend `128 passed`, cv-service
`36 passed`, frontend `73 passed`.

### 7.2.1 Backend (`backend/tests/`) — 128 pruebas (pytest)

La suite se agrupa por área de preocupación, sobre los ficheros de prueba reales:

| Área | Ficheros | Qué cubre |
|---|---|---|
| Autenticación | `test_auth.py`, `test_register_login.py` | registro, login, refresh, logout, revocación en bloque por reuso de token, JWT |
| Contrato | `test_contract_schemas.py`, `test_signing.py` | esquemas del contrato en ambas direcciones; firma y verificación HMAC-SHA256 |
| API de intentos | `test_create_attempt.py`, `test_read_attempts.py`, `test_delete_attempt.py` | validación de la subida, creación del intento, consulta e historial, borrado GDPR y su orden |
| Integración con el cv-service | `test_cv_client.py`, `test_webhook.py` | cliente del cv-service; recepción idempotente del webhook firmado |
| Trabajos en segundo plano | `test_jobs.py` | reconciliador de sondeo, purga por retención |
| Infraestructura | `test_health.py`, `test_cors.py`, `test_models.py`, `test_storage.py`, `test_validation.py` | *health check*, CORS, modelos ORM, almacenamiento local, validación de ficheros |
| Extremo a extremo (API) | `test_end_to_end.py` | `test_full_lifecycle_upload_webhook_read_delete`: subida → webhook → lectura → borrado, contra `fake-cv-service` |

Se ejecuta con `cd backend && uv run --extra dev pytest` (el extra `dev` instala pytest, respx y
ruff).

### 7.2.2 cv-service (`cv-service/tests/`) — 36 pruebas (pytest)

Cuatro ficheros: `test_jobs.py`, `test_main.py`, `test_pipeline.py` y `test_security.py`. Siguen la
convención ya establecida en §6: **el código que depende de MediaPipe/OpenCV se verifica a mano
sobre vídeo real; la lógica pura sí lleva prueba automatizada** —cálculo de ángulos, transiciones de
la máquina de estados de repeticiones, curva de puntuación, códec de escritura de vídeo, autenticación
por `X-API-Key` y ciclo de vida de los *jobs*. Así, las 36 pruebas cubren el núcleo determinista y
§7.5 cubre lo que pytest no puede alcanzar estructuralmente. El propio `test_pipeline.py` deja
constancia de esta frontera: comprueba con datos sintéticos que el vídeo se escribe con un códec que
el navegador decodifica, «para que un fallo de códec se detecte aquí y no a mano viendo un vídeo que
no reproduce».

### 7.2.3 Frontend (`frontend/tests/`) — 73 pruebas unitarias (Vitest) + 1 extremo a extremo (Playwright)

La cifra 73 es la que reporta `vitest run`; un recuento crudo de `it(`/`test(` la subestima porque no
ve los casos parametrizados, así que se usa el número del *runner*.

- **Unitarias** (`frontend/tests/unit/`): componentes (`app-shell`, `attempt-result`,
  `attempt-history-list`, `video-upload-form`, `protected-route`), *hooks* (`use-attempt`,
  `use-attempts`, `use-attempt-video`), librería (`api-client` con su *refresh-and-retry*,
  `auth-context`, y las tres tablas de mensajes `failure` / `upload-error` / `form-error`) y páginas
  (`login`, `register`, `home`, `attempt-detail`).
- **Extremo a extremo** (`frontend/tests/e2e/full-flow.spec.ts`): un único escenario Playwright —
  registrarse → cerrar sesión → volver a iniciar sesión → subir `squat.mp4` → esperar a que el
  estado sea `completed` o `failed` → borrar el intento. Ejercita el navegador real contra un
  backend y un `fake-cv-service` reales.

Se ejecuta con `cd frontend && npm test` (Vitest) y `npx playwright test` (extremo a extremo, que
requiere backend, `fake-cv-service` y Postgres levantados). Dos matices del entorno de evaluación:
`vitest.setup.ts` instala un *shim* de `localStorage` porque en la versión de Node usada acaba
resolviendo a `undefined`, y `vitest.config.ts` excluye los ficheros sombra `**/._*` (AppleDouble)
que macOS escribe junto a cada fichero nuevo por vivir el repositorio en un volumen exFAT.

### 7.2.4 Integración continua

`.github/workflows/deploy-backend.yml` **despliega, no prueba**. En cada *push* a `main` que toque
`backend/`, `cv-service/` o los ficheros de despliegue —y también a mano vía `workflow_dispatch`—
entra por SSH a la VM y ejecuta `docker compose … up -d --build`. No hay ningún *job* de pytest,
vitest, Playwright ni *lint* en el flujo; es el único *workflow* del repositorio. **La suite es, por
tanto, una barrera local, no automatizada en CI**: se ejecuta a mano antes de fusionar, y el registro
de `git log` y las revisiones de rama lo respaldan, pero no existe una ejecución reproducible en el
servidor que garantice que `main` pasa las pruebas en cualquier momento. Se retoma como limitación en
§7.6.

**Totales (a fecha de `d14bd8c`):** 128 + 36 + 73 = **237 pruebas automatizadas** y **2 pruebas
extremo a extremo** (una de nivel de API en el backend, `test_full_lifecycle_upload_webhook_read_delete`;
una de nivel de navegador en el frontend, `full-flow.spec.ts`). Las tres suites se ejecutaron el
01/09/2026 con este resultado.

## 7.3 Verificación de requisitos funcionales

Esta sección traza cada caso de uso del §4 a la evidencia de que funciona: qué pruebas automatizadas
lo ejercitan, si alguna de las dos pruebas extremo a extremo lo recorre y qué comprobación manual se
hizo a través de la interfaz en ejecución. Los nombres de la tabla son ficheros de prueba reales
—de `backend/tests/`, `frontend/tests/unit/` y `frontend/tests/e2e/`— citados sin extensión.

| Caso de uso | Automatizadas | Extremo a extremo | Verificación manual |
|---|---|---|---|
| CU-1: Registrarse | `test_register_login` (backend); `register-page`, `auth-context` (frontend) | `full-flow` (paso de registro) | alta de cuentas reales por navegador en varias sesiones |
| CU-2: Iniciar sesión | `test_register_login` (backend); `login-page`, `auth-context`, `protected-route` (frontend) | `full-flow` (cerrar sesión → volver a entrar) | inicio de sesión real por navegador |
| CU-3: Cerrar sesión | `test_register_login` (backend, revoca el *refresh token*); `app-shell`, `auth-context` (frontend) | `full-flow` (paso de cierre de sesión) | cierre de sesión por navegador |
| CU-4: Subir video de un intento | `test_create_attempt`, `test_validation` (backend); `video-upload-form`, `upload-error-messages` (frontend) | `test_end_to_end` (nivel de API) y `full-flow` (navegador) | subidas reales del *fixture* y de clips propios (§7.5) |
| CU-5: Consultar resultado de un intento | `test_read_attempts`, `test_webhook` (backend); `attempt-result`, `use-attempt`, `use-attempt-video` (frontend) | `test_end_to_end` y `full-flow` (espera a estado `completed`/`failed`) | reproducción del video anotado real; bug de códec corregido en `eeae94a` (§6.1.5, §7.5) |
| CU-6: Ver historial de intentos | `test_read_attempts` (backend, paginación por cursor); `attempt-history-list`, `use-attempts` (frontend) | `test_end_to_end` (comprueba que el intento aparece en el historial) | revisión del historial por navegador |
| CU-7: Eliminar un intento (derecho al olvido / GDPR) | `test_delete_attempt` (backend, borrado cruzado backend↔cv-service y su orden) | `test_end_to_end` y `full-flow` (borrado final) | borrado verificado a mano contra el cv-service |

**Todos los CU tienen cobertura automatizada.** Las dos lagunas visibles —se señalan, no se
ocultan— están en las pruebas extremo a extremo. La e2e de navegador (`full-flow`) no comprueba la
vista de historial (CU-6) como paso propio: a nivel de API sí lo cubre `test_end_to_end`, y en el
navegador queda en manos de las pruebas unitarias (`attempt-history-list`, `use-attempts`) y del uso
manual. Y CU-7 no tiene prueba unitaria de frontend: se apoya en la suite del backend y en las dos
pruebas extremo a extremo. El resto de casos de uso está cubierto en los tres niveles.

## 7.4 Verificación de requisitos no funcionales

Cada RNF del §4 se contrasta aquí con la evidencia disponible: cómo se comprobó y qué resultado dio.
Los RNF con prueba automatizada citan ficheros reales de `backend/tests/`. Las cifras de RNF-2 y
RNF-3 se toman **literalmente de §4** (medición del 15/08/2026 con `benchmark_latencia.py`); esta
sección las reproduce como resultado de aquella medición, no las recalcula.

| RNF | Cómo se verificó | Resultado |
|---|---|---|
| RNF-1 · Formatos y tamaño de vídeo | `test_validation.py` (extensiones `.mp4`/`.mov`, códec H.264, tope de 100 MB, duración máxima de 60 s), más los límites de tamaño y duración que el cv-service aplica por su cuenta (`cv-service/main.py`) | **Cumplido**, con prueba automatizada en los dos servicios |
| RNF-2 · Latencia de análisis | `benchmark_latencia.py`, 15/08/2026, sobre `squat.mp4` (~13s) en la máquina de desarrollo (16 núcleos físicos / 22 lógicos); 3 tandas secuenciales | Latencia media **12.4s** (mín. 12.3s, máx. 12.4s), una relación de **~0.95x** la duración del vídeo, dominada por el procesamiento frame a frame de MediaPipe. Extrapolada linealmente a un vídeo de 60s: **~57s** de procesamiento puro. SLA propuesto: **menos de 90s** para un vídeo de 60s (§4 RNF-2). Sin SLA verificado en producción |
| RNF-3 · Capacidad concurrente | Mismo benchmark, niveles de concurrencia 1/2/3/4, 3 tandas cada uno, misma máquina | La latencia por job se mantuvo prácticamente plana hasta concurrencia 4 (**1.00x-1.06x** contra la línea base de concurrencia 1, máx. **14.9s** en una tanda): MediaPipe/OpenCV liberan el GIL lo suficiente para que los hilos del `BackgroundTask` corran en paralelo de verdad. Objetivo conservador para el destino de despliegue real (2 OCPU compartidos): **2 análisis simultáneos**, no como límite medido y sin confirmar sobre esa máquina (§4 RNF-3) |
| RNF-4 · Precisión del modelo | No aplica una métrica de *accuracy*: el pipeline es un sistema de reglas sobre umbrales de ángulo articular (§6.1), no un clasificador entrenado. El objetivo de §4 —fiabilidad de detección sobre un conjunto de vídeos de referencia— exigiría construir y etiquetar ese conjunto | **Queda sin cuantificar**: el conjunto de referencia no se construyó (se asume abiertamente en §7.6). La única evaluación disponible es la observación cualitativa sobre vídeo real de §7.5 |
| RNF-5 · Seguridad | `test_signing.py` (firma y verificación HMAC-SHA256 en ambos sentidos: cuerpo manipulado, secreto erróneo, *timestamp* caducado o futuro); `test_webhook.py` (el backend rechaza webhooks sin firma o con firma inválida, verifica antes de buscar el intento y es idempotente); `test_register_login.py` (el caso `test_refresh_detects_reuse…`: revocación en bloque de toda la familia de *refresh tokens* ante detección de reuso); `test_cv_client.py` (la cabecera `X-API-Key` viaja en el envío del job, el borrado y el proxy de vídeo) | **Cumplido**, con prueba automatizada para cada mecanismo |
| RNF-6 · Disponibilidad | La aplicación está en producción sobre el fallback gratuito de GCP (`fake-cv-service`), con TLS real de Let's Encrypt y CI de despliegue autosostenido | **Sin SLA medido**: no hay monitorización de *uptime*. El objetivo de disponibilidad de §4 queda sin verificar |
| RNF-7 · Accesibilidad (WCAG 2.1 AA) | El rediseño del frontend de 2026-08-25 recalculó **todos** los ratios de contraste con la fórmula de luminancia relativa (no a ojo) y una revisión final los volvió a comprobar contra las superficies compuestas reales, corrigiendo tres pares de color que fallaban AA (spec de rediseño del frontend, ruta docs/superpowers/specs/2026-08-25-frontend-redesign-design.md); los componentes proceden de shadcn/ui, accesibles por defecto | **Conformidad AA razonada, no auditada**: no se ejecutó Lighthouse ni axe, ni se hizo una pasada con lector de pantalla |

**Caveat transversal.** Los benchmarks de RNF-2 y RNF-3 se midieron en una única máquina de
desarrollo de 16 núcleos, no en el destino de despliegue real (2 OCPU compartidos con el backend y
Postgres). Las cifras no se trasladan directamente, y los objetivos propuestos (SLA de menos de 90s,
2 análisis simultáneos) están pendientes de re-medir con `benchmark_latencia.py` sobre esa máquina.
Ya se advierte en §4; §7.6 lo retoma como amenaza a la validez.

## 7.5 Evaluación del pipeline sobre vídeo real

El pipeline de análisis de movimiento no se evalúa con una cifra de *accuracy* (§7.1, §7.4 RNF-4):
es un sistema de reglas deterministas, no un clasificador entrenado, y no existe un conjunto de
vídeos etiquetados contra el que medirlo. Lo que sí hubo, a lo largo del proyecto, fue una serie de
**pruebas manuales sobre vídeo de sentadilla real**: alguien ejecutaba el pipeline sobre un clip
concreto, miraba los resultados fotograma a fotograma y anotaba dónde acertaba y dónde fallaba. Esta
sección recoge esas observaciones en orden cronológico. Es una evaluación **exploratoria** —pocos
vídeos, sin verdad-terreno— y su alcance se acota en §7.5.4.

### 7.5.1 El vídeo de referencia (`squat.mp4`)

El primer análisis real sobre `backend/tests/fixtures/squat.mp4` se hizo el 04/08/2026, antes del
arreglo de códec. La segmentación en repeticiones funcionó: **se detectaron correctamente las 6
repeticiones** del clip. Pero el ángulo mínimo de rodilla de cada repetición volvió en torno a
**39°–44°**, muy por debajo del umbral de profundidad entonces vigente (una banda de dos límites
`GOOD_DEPTH_MIN`/`GOOD_DEPTH_MAX`), de modo que las 6 repeticiones puntuaron entre **7 y 22 sobre
100** (global ≈ 14/100) *pese a* una detección limpia.

Esa contradicción —una sentadilla bien ejecutada y bien contada, puntuada como si fuera pésima— es
lo que sacó a la luz la anomalía de la curva de puntuación: el *score* penalizaba bajar **más**
profundo que la banda ideal. Alejandro la corrigió después colapsando la banda de dos límites en un
único umbral `GOOD_DEPTH_ANGLE_DEG` (*commit* `aefbc6f`; el mensaje de ese *commit* cita
explícitamente el caso «un *squat* real, limpio y de 39–44° que puntuaba 7–22/100»), cambio ya
documentado en §6.1.4.

`squat.mp4` es un clip de archivo con marca de agua de Getty, apto solo para las pruebas
automatizadas y no para las figuras de interfaz del §5, que usan un clip de sentadilla al aire
libre grabado por el propio usuario.

### 7.5.2 El bug de códec (solo visible en un navegador real)

El vídeo anotado que produce el pipeline se veía como un **cuadro en blanco** en el reproductor del
frontend. La causa: el pipeline escribía la salida con `cv2.VideoWriter_fourcc(*"mp4v")` —MPEG-4
Part 2—, un códec que el elemento `<video>` de los navegadores no decodifica (solo aceptan
H.264/AVC, VP8/VP9, AV1, y HEVC en Safari).

**Nadie lo había detectado antes** porque todas las pruebas anteriores del camino de vídeo usaban
`fake-cv-service`, que devuelve una URL prefabricada y nunca escribe un vídeo real. Fue la primera
vez que alguien pulsó *play* sobre un vídeo producido por el `cv-service` real en un navegador real.
El arreglo fue el *commit* `eeae94a`, que cambió el códec a `avc1` (H.264 real con este *build* de
OpenCV, sin post-proceso con `ffmpeg`); el códec en sí está documentado en §6.1.5.

Este es el ejemplo canónico, dentro del proyecto, de un defecto que **ninguna prueba automatizada
podía encontrar**: no lo veían ni las pruebas del backend (que hablan con `fake-cv-service`) ni las
del `cv-service` (que verifican la lógica pura, no la reproducción en navegador) ni la e2e de
Playwright (que también corre contra `fake-cv-service`). Hizo falta una persona mirando la interfaz
real.

### 7.5.3 Vídeo de cámara frontal (27/08/2026)

Un clip aportado por el usuario: una sentadilla profunda grabada con la **cámara de frente**, fuera
de la suposición de cámara lateral (plano sagital) sobre la que está construido el pipeline (§6.1).
El clip era de 1080p, unos 56 s y unos 120 MB —por encima del tope de 100 MB de la API—, así que se
ejecutó directamente a través de la función `analizar_video` en el entorno virtual, sin pasar por
HTTP, y reescalado antes a 720p para acelerar el procesamiento (unos 25 s).

El resultado fue un **éxito parcial con fallos instructivos**:

- Las **15 sentadillas reales** —una vez que la persona estaba quieta y dentro del encuadre— se
  siguieron bien *incluso de frente*: ángulos mínimos de rodilla entre **78° y 94°**, puntuadas
  correctamente y sin falsos errores de forma. MediaPipe reconstruye una pose 3D estimada, así que
  la flexión de rodilla es parcialmente recuperable de frente.
- Pero el segmentador contó **5 «repeticiones» espurias**: 4 en los primeros ~1,4 s (la persona
  entrando en cuadro y colocándose —una de ellas con un `min_knee_angle_deg` de **5,1°**, físicamente
  imposible, que puntuó **100**) y 1 al final (al levantarse).
- `excessive_forward_lean` se disparó sobre algunas de esas repeticiones de ruido, pese a que una
  inclinación de torso es estructuralmente indetectable desde una cámara frontal.

Los fallos reales que esta prueba puso de manifiesto están **todos en el dominio de Alejandro**
según el reparto de trabajo entre pistas (§3):

1. No hay una puerta de duración mínima ni de plausibilidad por repetición.
2. `score_from_angle` premia profundidades físicamente imposibles: le falta un suelo en torno a
   30°–40°.
3. Las fases de colocación y de salida contaminan el conteo de repeticiones: haría falta una puerta
   de N fotogramas consecutivos de pie, o descartar el primer y el último ~1,5 s.
4. `excessive_forward_lean` no debería evaluarse sin la garantía de una cámara lateral.

De estos, el problema de dirección de `excessive_forward_lean` ya estaba recogido —por otra vía— en
el mensaje de seguimiento a Alejandro del 20/08/2026, junto con el riesgo de que *landmarks* casi
coincidentes disparen el error por ruido de sub-píxel. Los puntos 1, 2 y 3, y el encuadre concreto
del punto 4 (cámara frontal), provienen de las notas de esta sesión de prueba y quedan como material
para la siguiente comunicación con Alejandro.

### 7.5.4 Alcance de esta evaluación

Esta evaluación del pipeline abarcó **unos 3 vídeos, sin etiquetas de verdad-terreno, y de forma
exploratoria**: no hubo protocolo, ni conjunto de referencia, ni repetición sistemática. Sirve para
**caracterizar modos de fallo** —la anomalía de la curva de puntuación, el bug de códec, el ruido de
colocación, la fragilidad ante cámaras no laterales— pero **no produce una cifra de fiabilidad** del
conteo de repeticiones ni de la detección de errores de forma. Esa limitación, y su consecuencia
sobre el objetivo de RNF-4, se recogen en §7.6.
