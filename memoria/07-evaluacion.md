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
