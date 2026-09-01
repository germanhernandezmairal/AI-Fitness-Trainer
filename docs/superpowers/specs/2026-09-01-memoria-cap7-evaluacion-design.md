# Design: Memoria — Chapter 7 (Evaluación)

**Date:** 2026-09-01
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED (2026-09-01)
**Related:** `memoria-ada-outline.md` §7 (scaffolding this chapter expands);
`memoria/03-planificacion.md`, `memoria/04-requisitos.md`, `memoria/05-diseno.md`,
`memoria/06-implementacion.md` (the four existing chapters — set the per-chapter-spec,
file-location, Spanish-language and numbered-heading precedent; §4 in particular owns the CU-1…CU-7
and RNF-1…RNF-7 catalogues this chapter traces back to, and §6.1.6 already frames why no ML metric
applies); the real test suites (`backend/tests/`, `cv-service/tests/`, `frontend/tests/`),
`cv-service/scripts/benchmark_latencia.py`, `.github/workflows/deploy-backend.yml`,
`docs/2026-08-11-alejandro-cv-form-error-detection-message.md`,
`docs/2026-08-20-alejandro-cv-form-error-detection-followup-message.md` (capture some of the manual
CV-testing findings), and git history (the test-first commit record).

---

## 0. Context and goal

Same per-chapter approach as Ch.3–6: the memoria's 12 chapters are largely independent, so each is
its own sub-project (brainstorm → spec → plan → SDD). This design covers only **Chapter 7
(Evaluación)**.

Per `memoria-ada-outline.md` §7, this chapter is about **test-case design that traces back to the
requirements, plus the actual results and an evaluation of the project** — not a test plan in the
abstract, but what was really verified and what was found.

**Basis decided with the user during brainstorming (2026-09-01): retrospective only.** The chapter
documents the evaluation that *already happened* — the automated suites, the two end-to-end tests,
the manual CV-pipeline testing on real video, and the one benchmark run (2026-08-15) — and states
its gaps honestly. **No new measurement work**: no labeled-clip validation dataset is built, the
benchmark is not re-run, no new test campaign is mounted. This matches the project's frozen-MVP
posture (the deployment is frozen on the free-tier fallback; the plan of record is "finish via
memoria then start a new project").

**Structure decided with the user: six sections** (§7.1–§7.6, below).

**Outline-vs-reality corrections this chapter makes** (same posture as Ch.3–6):

- The outline's *"AI-side evaluation: model accuracy / validation against labeled clips"* does not
  apply as written. The CV pipeline is a **deterministic rules system** on top of a pre-trained
  MediaPipe detector (§6.1.6, §4 RNF-4) — there is no trained model, no labeled dataset, and no
  accuracy/precision/recall figure. §7.1 states this; §7.5 reports the behavioural evaluation that
  *was* done instead (real video, exploratory).
- The outline implies CI runs the tests. It does **not** — `.github/workflows/deploy-backend.yml`
  only SSHes to the VM and runs `docker compose up --build`. Tests are a **local-only gate**.
  §7.2 and §7.6 both say so.
- "Redis, PyTorch, TensorFlow" etc. from the pre-code outline — not used (already corrected in
  §5/§6; §7 does not re-litigate, just doesn't cite them).

The chapter is written **in Spanish**, numbered headings (`## 7.1`, `### 7.5.1` where needed), new
file `memoria/07-evaluacion.md`, `NN-nombre.md` pattern. `memoria-ada-outline.md` stays untouched.

---

## 1. Section 7.1 — Estrategia de evaluación

Short framing section (~200–300 words). Points to make:

- **Two evaluation targets with different natures.**
  1. *The web application* — its behaviour is defined by the Ch.4 requirements (CU-1…CU-7,
     RNF-1…RNF-7), so it is evaluated by **verification against those requirements**: automated
     tests per component, two end-to-end tests, and manual checks through the running UI.
  2. *The movement-analysis pipeline* — a deterministic rules system (§6.1), not a trained
     classifier. "Accuracy" in the ML sense does not apply. It is evaluated by **observing its
     behaviour on real squat video** and recording where it succeeds and where it breaks.
- **Methodology.** Every feature and every memoria chapter was built test-first via the
  `superpowers` TDD / subagent-driven-development workflow (§3 narrates this; `git log` shows the
  test commits preceding or accompanying implementation commits). The automated suites are the
  durable artefact of that process, not a retrofit.
- **What was deliberately not done, and why it is defensible for this TFG:**
  - No labeled-clip validation dataset for the CV pipeline — building and labelling one is a
    project in itself; out of scope for a two-person TFG with a frozen MVP. The consequence
    (RNF-4's reliability objective stays unquantified) is owned openly in §7.6.
  - No formal test campaign beyond the suites that shipped with each feature — the MVP is frozen,
    so there is no new code to campaign against.
  - The CV-pipeline evaluation (§7.5) is **exploratory**, not systematic: a handful of videos, no
    ground-truth labels.

---

## 2. Section 7.2 — Pruebas automatizadas

Per-component breakdown. Numbers stated as "a fecha de <commit hash>" so they are falsifiable.

### 2.1 Backend (`backend/tests/`) — 128 pruebas (pytest)

Group the suite by concern, citing the real test files:

| Área | Ficheros | Qué cubre |
|---|---|---|
| Autenticación | `test_auth.py`, `test_register_login.py` | registro, login, refresh, logout, revocación por reuso, JWT |
| Contrato | `test_contract_schemas.py`, `test_signing.py` | esquemas del contrato en ambas direcciones; firma/verificación HMAC-SHA256 |
| API de intentos | `test_create_attempt.py`, `test_read_attempts.py`, `test_delete_attempt.py` | validación de subida, creación, consulta/historial, borrado GDPR y su orden |
| Integración CV | `test_cv_client.py`, `test_webhook.py` | cliente del cv-service, recepción idempotente del webhook firmado |
| Trabajos en segundo plano | `test_jobs.py` | reconciliador de sondeo, purga por retención |
| Infraestructura | `test_health.py`, `test_cors.py`, `test_models.py`, `test_storage.py`, `test_validation.py` | health check, CORS, modelos ORM, almacenamiento local, validación de ficheros |
| Extremo a extremo (API) | `test_end_to_end.py` | `test_full_lifecycle_upload_webhook_read_delete`: subida → webhook → lectura → borrado, contra `fake-cv-service` |

Run: `cd backend && uv run --extra dev pytest` (`--extra dev` installs pytest/respx/ruff).

### 2.2 cv-service (`cv-service/tests/`) — 36 pruebas (pytest)

`test_jobs.py`, `test_main.py`, `test_pipeline.py`, `test_security.py`. State the file's own
established convention (§6): **MediaPipe/OpenCV-dependent code is verified by hand on real video;
pure logic (angle math, state-machine transitions, scoring curve, codec, API auth, job lifecycle)
gets a real pytest.** So the 36 tests cover the deterministic core,
and §7.5 covers what pytest structurally cannot.

### 2.3 Frontend (`frontend/tests/`) — 73 pruebas unitarias (Vitest) + 1 e2e (Playwright)

(73 is what `vitest run` reports — more than a raw `it(`/`test(` grep, which misses parametrized
cases. Use the runner's number.)

- **Unitarias** (`frontend/tests/unit/`): componentes (`app-shell`, `attempt-result`,
  `attempt-history-list`, `video-upload-form`, `protected-route`), hooks (`use-attempt`,
  `use-attempts`, `use-attempt-video`), librería (`api-client` con refresh-and-retry,
  `auth-context`, las tres tablas de mensajes `failure`/`upload-error`/`form-error`), y páginas
  (`login`, `register`, `home`, `attempt-detail`).
- **Extremo a extremo** (`frontend/tests/e2e/full-flow.spec.ts`): un único escenario Playwright —
  registrarse → cerrar sesión → volver a iniciar sesión → subir `squat.mp4` → ver el resultado
  (`completed`/`failed`) → borrar el intento. Ejercita el navegador real contra backend +
  `fake-cv-service` reales.

Run: `cd frontend && npm test` (Vitest) y `npx playwright test` (e2e, requiere backend +
`fake-cv-service` + Postgres levantados). Note the Node-26 `localStorage` shim (`vitest.setup.ts`)
and the `**/._*` (exFAT AppleDouble) exclude in `vitest.config.ts` — one sentence, as
evaluation-environment caveats.

### 2.4 Integración continua

`.github/workflows/deploy-backend.yml` **despliega, no prueba**: en cada push a `main` que toque
`backend/`, `cv-service/` o los ficheros de despliegue, entra por SSH a la VM y ejecuta
`docker compose … up -d --build`. No hay job de pytest, vitest, Playwright ni lint. **La suite es
una barrera local, no automatizada en CI** — se ejecuta a mano antes de fusionar (el registro de
`git log` y las revisiones de rama lo respaldan, pero no hay ejecución reproducible en el servidor).
Esto se retoma como limitación en §7.6.

**Totales a fecha de `<commit>`:** 128 + 36 + 73 = **237 pruebas automatizadas** y **2 pruebas
extremo a extremo** (una de API en el backend, una de navegador en el frontend). (Verified by
running all three suites on 2026-09-01: backend `128 passed`, cv-service `36 passed`, frontend
`73 passed`.)

---

## 3. Section 7.3 — Verificación de requisitos funcionales

One **traceability matrix**: each CU from §4 → the evidence that it works. Markdown table,
columns: `CU` · `Pruebas automatizadas` · `Extremo a extremo` · `Verificación manual`.

Row content (to be filled from a fresh grep of the test files during writing — the plan verifies
each cell):

| CU | Automatizadas | E2E | Manual |
|---|---|---|---|
| CU-1 Registrarse | `test_register_login.py`, `register-page.test.tsx` | ambas e2e (paso de registro) | flujo por navegador (varias sesiones) |
| CU-2 Iniciar sesión | `test_register_login.py`, `test_auth.py`, `login-page.test.tsx`, `auth-context.test.tsx` | frontend e2e (logout→login) | idem |
| CU-3 Cerrar sesión | `test_auth.py` (revocación), `app-shell.test.tsx` | frontend e2e | idem |
| CU-4 Subir vídeo | `test_create_attempt.py`, `test_validation.py`, `video-upload-form.test.tsx`, `use-attempts.test.tsx` | ambas e2e | subidas reales (fixture + clips propios), §7.5 |
| CU-5 Consultar resultado | `test_read_attempts.py`, `test_webhook.py`, `attempt-result.test.tsx`, `use-attempt*.test.*` | ambas e2e | reproducción real del vídeo anotado (bug de códec `eeae94a`), §7.5 |
| CU-6 Ver historial | `test_read_attempts.py`, `attempt-history-list.test.tsx`, `home-page.test.tsx` | — (no cubierto explícitamente) | flujo por navegador |
| CU-7 Eliminar intento (GDPR) | `test_delete_attempt.py`, `test_end_to_end.py` | frontend e2e (borrado final) | borrado cruzado backend↔cv-service verificado a mano |

Short prose after the table: **every CU has automated coverage**; the one visible gap is that the
browser e2e does not assert the history view as its own step (CU-6), covered only by unit tests and
manual use — noted, not hidden.

---

## 4. Section 7.4 — Verificación de requisitos no funcionales

Per-RNF evidence, prose or a compact table (`RNF` · `Cómo se verificó` · `Resultado`). Content:

- **RNF-1 (formatos y tamaño):** `test_validation.py` (extensiones, códec H.264, 100 MB, 60 s) +
  los límites independientes del cv-service. **Cumplido, con prueba automatizada.**
- **RNF-2 (latencia):** `benchmark_latencia.py`, 2026-08-15, sobre `squat.mp4` (~13 s) en la
  máquina de desarrollo (16 núcleos físicos): **media 12.4 s** (mín. 12.3, máx. 12.4), ≈0.95× la
  duración del vídeo, dominado por MediaPipe. Extrapolado a 60 s → ~57 s; SLA propuesto <90 s.
  (Cifras ya en §4 RNF-2 — §7 las cita como el resultado de la medición, no las recalcula.)
- **RNF-3 (concurrencia):** mismo benchmark, niveles 1–4: latencia por job **plana hasta
  concurrencia 4** (1.00–1.06× la línea base, máx. 14.9 s) — MediaPipe/OpenCV liberan el GIL.
  Objetivo conservador para el destino real (2 OCPU compartidos): 2 análisis simultáneos, sin
  confirmar sobre esa máquina.
- **RNF-4 (precisión):** sistema de reglas, **sin métrica de accuracy**. El objetivo de §4
  ("fiabilidad de detección sobre un set de referencia") **queda sin cuantificar** — no se
  construyó el set. La evaluación cualitativa disponible es §7.5.
- **RNF-5 (seguridad):** `test_signing.py` (HMAC en ambos sentidos), `test_auth.py` (revocación en
  bloque por reuso), `test_cv_client.py`/`test_webhook.py` (`X-API-Key`, proxy de vídeo
  autenticado). **Cumplido, con pruebas automatizadas** para cada mecanismo.
- **RNF-6 (disponibilidad):** la aplicación está **en producción** sobre el fallback gratuito de
  GCP (`fake-cv-service`), con TLS real y CI de despliegue autosostenido. **Sin SLA medido** — no
  hay monitorización de uptime.
- **RNF-7 (accesibilidad):** el rediseño de 2026-08-25 recalculó **todos los ratios de contraste
  con luminancia relativa real** (no a ojo) y una revisión final volvió a comprobarlos contra las
  superficies compuestas reales, corrigiendo tres que fallaban AA
  (`docs/superpowers/specs/2026-08-25-frontend-redesign-design.md`). **No se ejecutó** una auditoría
  automatizada
  (Lighthouse/axe) ni una revisión con lector de pantalla — conformidad AA *razonada*, no
  *auditada*.
- **Caveat transversal:** los benchmarks son de una única máquina de 16 núcleos, no del destino de
  despliegue (2 OCPU compartidos) — las cifras no se trasladan directamente. Ya dicho en §4; §7 lo
  repite como amenaza a la validez.

---

## 5. Section 7.5 — Evaluación del pipeline sobre vídeo real

Narrative section. **Provenance note for the plan:** the detailed findings below come from
project-session records and the two Alejandro message docs, not fully from the repo — the plan must
flag these paragraphs for the user to sanity-check against their own memory of the test runs, and
cite the commits/docs that do corroborate each point.

Content, roughly chronological:

### 5.1 El vídeo de referencia (`squat.mp4`)

- Primer análisis real (2026-08-04, previo al fix de códec): **6 repeticiones detectadas
  correctamente**. Pero los ángulos mínimos volvieron ~39–44°, muy por debajo del entonces
  `GOOD_DEPTH_MIN`, así que las 6 puntuaron 7–22 (global ~14/100) pese a una detección limpia →
  **surgió la anomalía de la curva de puntuación** (penalizaba pasarse de profundo). Corregida
  después por Alejandro colapsando la banda a un único umbral (`aefbc6f`), documentado en §6.1.4.
- Es un clip de stock con marca de agua (Getty) — sólo apto para pruebas, no para las figuras del
  §5 (que usan un clip propio del usuario). Nota de una frase.

### 5.2 El bug de códec (sólo visible en navegador real)

- El vídeo anotado se veía como un cuadro en blanco en el reproductor. Causa: `mp4v` (MPEG-4 Part
  2), que los navegadores no decodifican. **Nadie lo había detectado antes** porque toda prueba
  previa del camino de vídeo usaba `fake-cv-service`, que nunca escribe un vídeo real — fue la
  primera vez que alguien pulsó *play* sobre un vídeo del pipeline real. Fix `eeae94a` (`avc1`).
  Este es el ejemplo canónico de un fallo que **ninguna prueba automatizada del proyecto podía
  encontrar** y que sólo apareció con un humano mirando la UP real.

### 5.3 Vídeo de cámara frontal (2026-08-27)

- Clip propio, sentadilla profunda, **vista frontal** (fuera de la suposición sagital del pipeline).
  Ejecutado directamente vía `analizar_video` (120 MB > límite de la API).
- **Éxito parcial, fallos instructivos:** las **15 sentadillas reales** (una vez estático y en
  cuadro) se siguieron bien incluso de frente — ángulos mínimos 78–94°, puntuadas correctamente,
  sin falsos errores de forma — porque MediaPipe reconstruye una pose 3D estimada. Pero el
  segmentador contó **5 "repeticiones" espurias:** 4 en los primeros 1.4 s (entrar en cuadro /
  colocarse, una con un imposible `min_knee_angle_deg: 5.1` puntuado 100) + 1 al final (levantarse).
  `excessive_forward_lean` se disparó sobre esas reps de ruido pese a ser estructuralmente
  indetectable desde una cámara frontal.
- Fallos reales que esto expuso, **todos del dominio de Alejandro** por el reparto de trabajo (§3):
  (1) sin puerta de duración/plausibilidad mínima por rep; (2) `score_from_angle` premia
  profundidades físicamente imposibles (falta un suelo ~30–40°); (3) las fases de colocación/salida
  contaminan el conteo; (4) `excessive_forward_lean` no debería evaluarse sin garantía de cámara
  lateral. Recogidos como material de limitaciones y para la siguiente nota a Alejandro.

### 5.4 Alcance de esta evaluación

Una frase honesta: **N ≈ 3 vídeos, sin etiquetas de verdad-terreno, exploratoria.** No sustituye a
una validación sistemática; sirve para caracterizar los modos de fallo, no para dar una cifra de
fiabilidad.

---

## 6. Section 7.6 — Limitaciones y amenazas a la validez

Bulleted, honest, cross-referencing the earlier sections. Each item = the limitation + its
consequence:

- **Sin dataset etiquetado del pipeline de CV** → RNF-4 sin cuantificar; la fiabilidad de conteo y
  de detección de errores de forma no tiene número, sólo la caracterización cualitativa de §7.5.
- **Un único vídeo de fixture** para las pruebas extremo a extremo automatizadas; el único clip
  real no marcado es propiedad del usuario. Poca diversidad de entrada probada de forma
  reproducible.
- **Benchmarks de una sola máquina** (portátil de desarrollo de 16 núcleos), no del destino real
  (2 OCPU compartidos con backend y Postgres) → RNF-2/RNF-3 no se trasladan; los objetivos
  propuestos son de partida, no medidos sobre producción.
- **CI no ejecuta la suite** → las regresiones sólo las detecta la disciplina local; no hay una
  garantía reproducible en el servidor de que `main` pase las 237 pruebas en cualquier momento.
- **Evaluación del pipeline exploratoria** (§7.5): N pequeño, sin verdad-terreno, sin protocolo.
- **Accesibilidad razonada, no auditada** → conformidad AA argumentada con matemática de contraste,
  sin Lighthouse/axe ni prueba con lector de pantalla.
- **Sin monitorización de producción** → RNF-6 sin SLA medido; no se sabe el uptime real del
  fallback.

Closing sentence: estas limitaciones son coherentes con el alcance (TFG de dos personas, MVP
congelado, despliegue gratuito) y se recogen aquí explícitamente en lugar de presentar la
evaluación como más completa de lo que es. Varias alimentan §10 (Conclusiones — qué se haría
distinto).

---

## 7. Diagrams and tables

- **No Mermaid, no LaTeX.**
- **2–3 Markdown tables:** the backend-suite concern table (§7.2.1), the CU traceability matrix
  (§7.3), optionally the RNF table (§7.4). Everything else prose.
- No source-code blocks.

---

## 8. Out of scope (explicit)

- Re-explaining the requirements themselves (that's §4) or the implementation (§6) — §7
  cross-references and traces, does not restate.
- Costs (§8), legal/data-protection evaluation (§9), overall project conclusions and
  what-I'd-do-differently (§10) — §7.6 may *feed* §10 but does not pre-empt it.
- Any new test, benchmark, or dataset — retrospective only, per the brainstorming decision.

---

## 9. Testing / verification approach

Documentation chapter — "testing" means factual accuracy, same bar as Ch.3–6:

- Every test count re-derived from a fresh run or a fresh `grep 'def test_'` /
  `grep -c 'it(\|test('` immediately before writing, and stated as "a fecha de `<commit>`".
- Every test-file name and every CU/RNF cross-reference re-checked against the current source.
- The CI claim ("deploys, does not test") verified against `.github/workflows/deploy-backend.yml` as
  it stands, not assumed.
- The benchmark numbers quoted exactly as they appear in `memoria/04-requisitos.md` (single source
  of truth — §7 must not introduce a second, drifting copy).
- **§7.5 paragraphs flagged for user sanity-check** — they rest on session records; the user
  confirms each against their own memory and against the commits/docs cited.
- Whole-chapter review (opus, matching Ch.3–6's final-review step) before merge, checking every
  claim against the source it cites, with specific attention to §7.5 (other track's domain) and the
  traceability matrix cells.

---

## 10. Open questions

None — the two real decisions (retrospective-only basis; six-section structure) were resolved with
the user during brainstorming (2026-09-01) before this doc was written.
