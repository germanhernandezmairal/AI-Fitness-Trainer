# Memoria Chapter 7 (Evaluación) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `memoria/07-evaluacion.md`, the finished Chapter 7 (Evaluación) of the project's
academic report — how the system was evaluated (automated suites, two end-to-end tests, manual
CV-pipeline testing on real video, the 2026-08-15 benchmark), traced back to the Chapter 4
requirements, with the actual results and an honest account of the gaps — in Spanish, grounded in
the real test suites and CI config.

**Architecture:** This is a writing deliverable, not code. Each task's "test cycle" is a
source-of-truth verification (run a suite, `grep`/`read` the real test files or
`.github/workflows/`) *before* writing the corresponding prose/table, and a re-check *after*, so
every count, file name, CU/RNF cross-reference and benchmark number is traceable to something real.
No automated test suite is added — "passing" means the written content matches the verified fact and
the chapter still renders through `memoria/build-pdf.sh`.

**Tech Stack:** Markdown (2–3 tables, prose otherwise). No Mermaid, no LaTeX. No code changes to
`backend/`, `frontend/`, or `cv-service/`.

**Spec:** `docs/superpowers/specs/2026-09-01-memoria-cap7-evaluacion-design.md`

## Global Constraints

- Written entirely in Spanish (spec §0).
- Output file: `memoria/07-evaluacion.md` (new), `NN-nombre.md` pattern — `memoria-ada-outline.md`
  itself is NOT edited (spec §0).
- **Numbered headings** throughout: `## 7.1` … `## 7.6`, and `### 7.5.1` etc. where a section has
  subsections — matching the project-wide decision applied to Ch.3–6 (spec §0).
- **Retrospective only.** No new test, benchmark, or dataset is created. The chapter documents
  evaluation that already happened (spec §0, §8).
- **No source-code blocks.** Tables and prose only (spec §7).
- Benchmark numbers (RNF-2/RNF-3) are quoted **exactly as they appear in
  `memoria/04-requisitos.md`** — `memoria/07-evaluacion.md` must not introduce a second, drifting
  copy (spec §9).
- Cross-references to other chapters use the `§4`, `§5`, `§6.1.4` short form already used in Ch.6.
- The CV pipeline (§7.5 subject matter) is Alejandro's work (Datos/IA track); prose says so, and
  §7.5's failure-mode findings are attributed to his domain per the §3 work split (spec §5).
- Every test count stated as "a fecha de `<commit>`" with the real short hash of the commit the
  task is written on (spec §2, §9).
- Provenance HTML comment at the top of the file, same pattern as Ch.4/Ch.6 (an HTML comment
  `<!-- ... -->`, NOT a `>` blockquote — a blockquote renders as visible body text; this was a
  real Ch.3 review finding).

---

### Task 1: Chapter scaffold + §7.1 Estrategia de evaluación

**Files:**
- Create: `memoria/07-evaluacion.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `memoria/07-evaluacion.md` with the provenance comment, `# 7. Evaluación` H1, and
  `## 7.1 Estrategia de evaluación` fully written. Task 2 appends `## 7.2` after this content.

- [ ] **Step 1: Confirm the methodology claim is real**

Run: `git log --oneline --diff-filter=A -- 'backend/tests/*' 'cv-service/tests/*' 'frontend/tests/**' | tail -20`
and `git log --oneline | grep -iE 'test|tdd|TDD' | head -20`

Expected: test files were added alongside or before their implementation across the project's
history (the TDD/SDD workflow). If the history does not clearly show test-first commits, soften
the §7.1 wording from "every feature was built test-first" to "the project used a test-first
workflow for most features (§3)". Note what you find for Step 3.

- [ ] **Step 2: Confirm §6.1.6 already frames the "no ML metric" point**

Run: `grep -n "accuracy\|precision\|recall\|deterministas\|squat-rules-v1\|entrenad" memoria/06-implementacion.md`

Expected: §6.1.6 states the pipeline is deterministic rules with no accuracy/precision/recall
figure. §7.1 refers back to it (`§6.1`), does not restate the argument.

- [ ] **Step 3: Write the file header and §7.1**

Create `memoria/07-evaluacion.md`:

```markdown
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
```

Adjust the methodology paragraph per Step 1's finding.

- [ ] **Step 4: Verify it renders**

Run: `cd memoria && ./build-pdf.sh && echo OK`
Expected: `Wrote .../memoria.pdf`, no `ERROR`. (The script picks up `07-evaluacion.md` automatically.)

- [ ] **Step 5: Commit**

```bash
git add memoria/07-evaluacion.md
git commit -m "docs(memoria): draft cap. 7 estrategia de evaluación"
```

---

### Task 2: §7.2 Pruebas automatizadas (+ CI)

**Files:**
- Modify: `memoria/07-evaluacion.md` (append `## 7.2`)

**Interfaces:**
- Consumes: `memoria/07-evaluacion.md` from Task 1 (ends after §7.1).
- Produces: `## 7.2 Pruebas automatizadas` with subsections `### 7.2.1` Backend, `### 7.2.2`
  cv-service, `### 7.2.3` Frontend, `### 7.2.4` Integración continua, and the totals line. Task 3
  appends `## 7.3`.

- [ ] **Step 1: Run all three suites and record the real numbers**

Run:
```
cd backend && uv run --extra dev pytest -q 2>&1 | tail -3
~/.venvs/ai-fitness-cv-service/bin/pytest -q cv-service/tests 2>&1 | tail -3   # run from repo root; adjust path if the venv moved
cd frontend && npm test 2>&1 | grep -E 'Test Files|Tests'
```
Expected (as of 2026-09-01): backend `128 passed`, cv-service `36 passed`, frontend `Tests 73 passed`.
**Use whatever the runners actually report** — if a number differs, use the real one everywhere in
§7.2 and in the §7.2 totals, and note it for Task 6's consistency pass.

- [ ] **Step 2: Inventory the backend suite by concern**

Run: `ls backend/tests/test_*.py` and, for any file whose scope is unclear,
`grep -n 'def test_' backend/tests/<file>.py | head`.

Expected files: `test_auth.py`, `test_contract_schemas.py`, `test_cors.py`, `test_create_attempt.py`,
`test_cv_client.py`, `test_delete_attempt.py`, `test_end_to_end.py`, `test_health.py`,
`test_jobs.py`, `test_models.py`, `test_read_attempts.py`, `test_register_login.py`,
`test_signing.py`, `test_storage.py`, `test_validation.py`, `test_webhook.py`. Confirm
`test_end_to_end.py` contains `test_full_lifecycle_upload_webhook_read_delete`.

- [ ] **Step 3: Confirm the cv-service test convention**

Run: `grep -n "MediaPipe\|mediapipe\|real video\|sintétic\|synthetic\|no MediaPipe\|hand-verified\|a mano" cv-service/tests/*.py cv-service/README.md`

Expected: the tests cover pure logic (jobs lifecycle, API/auth, angle & scoring math, codec);
MediaPipe-dependent inference is verified by hand on real video (the convention noted in §6). If
the tests actually do exercise MediaPipe, correct §7.2.2's wording to match.

- [ ] **Step 4: Confirm the CI workflow only deploys**

Run: `cat .github/workflows/deploy-backend.yml` and `ls .github/workflows/`

Expected: exactly one workflow, `deploy-backend.yml`; its only job SSHes to the VM and runs
`docker compose … up -d --build`; **no** `pytest` / `vitest` / `playwright` / `npm test` / `lint`
step anywhere; triggers on push to `main` touching `backend/**`, `cv-service/**`, or the deploy
files, plus `workflow_dispatch`. If a test job exists, rewrite §7.2.4 to describe it accurately.

- [ ] **Step 5: Confirm the frontend e2e scenario**

Run: `cat frontend/tests/e2e/full-flow.spec.ts`

Expected: a single `test(...)` — register → log out → log back in → upload
`backend/tests/fixtures/squat.mp4` → wait for `status: completed|failed` → delete. Runs against a
real backend + `fake-cv-service`.

- [ ] **Step 6: Write §7.2**

Append to `memoria/07-evaluacion.md`. Use the backend-concern table from spec §2.1 (translate the
"Área / Ficheros / Qué cubre" rows), the cv-service paragraph from spec §2.2, the frontend
paragraph + list from spec §2.3, the CI paragraph from spec §2.4, and close with:

```markdown
**Totales (a fecha de `<HASH>`):** 128 + 36 + 73 = **237 pruebas automatizadas** y **2 pruebas
extremo a extremo** (una de nivel de API en el backend, `test_full_lifecycle_upload_webhook_read_delete`;
una de nivel de navegador en el frontend, `full-flow.spec.ts`). Las tres suites se ejecutaron el
01/09/2026 con este resultado.
```

Replace `<HASH>` with `git rev-parse --short HEAD`. Replace the three numbers with Step 1's real
values if any differ.

- [ ] **Step 7: Verify facts and rendering**

Run: `grep -n "128\|36\|73\|237\|deploy-backend\|full-flow\|test_end_to_end" memoria/07-evaluacion.md`
then `cd memoria && ./build-pdf.sh && echo OK`.
Expected: every number matches Step 1; script writes the PDF with no `ERROR`.

- [ ] **Step 8: Commit**

```bash
git add memoria/07-evaluacion.md
git commit -m "docs(memoria): draft cap. 7 pruebas automatizadas y CI"
```

---

### Task 3: §7.3 Verificación de requisitos funcionales (traceability matrix)

**Files:**
- Modify: `memoria/07-evaluacion.md` (append `## 7.3`)

**Interfaces:**
- Consumes: `memoria/07-evaluacion.md` from Task 2 (ends after §7.2).
- Produces: `## 7.3 Verificación de requisitos funcionales` with one Markdown table (CU-1…CU-7 ×
  `Automatizadas` / `E2E` / `Manual`) and a short prose paragraph after it. Task 4 appends `## 7.4`.

- [ ] **Step 1: Verify the CU list from §4**

Run: `grep -n '^### 4\.1\.' memoria/04-requisitos.md`
Expected: `4.1.1 CU-1: Registrarse` … `4.1.7 CU-7: Eliminar un intento (derecho al olvido / GDPR)`.
Use these exact CU titles in the table's first column.

- [ ] **Step 2: For each CU, find the tests that exercise it**

Run these greps and record which files really contain matching tests (do not guess — a cell with a
file that does not test that CU is a factual error):
```
grep -rln "register\|/auth/register\|RegisterPage\|create account" backend/tests frontend/tests/unit
grep -rln "login\|/auth/login\|LoginPage\|log in\|log back in" backend/tests frontend/tests/unit
grep -rln "logout\|/auth/logout\|log out\|revoke" backend/tests frontend/tests/unit
grep -rln "create_attempt\|POST /v1/attempts\|upload\|VideoUploadForm\|validate_upload" backend/tests frontend/tests/unit
grep -rln "GET /v1/attempts/\|webhook\|AttemptResult\|use-attempt\b\|annotated" backend/tests frontend/tests/unit
grep -rln "history\|list attempts\|AttemptHistoryList\|HomePage\|home-page" backend/tests frontend/tests/unit
grep -rln "delete_attempt\|DELETE /v1/attempts\|erasure\|GDPR\|delete this attempt" backend/tests frontend/tests/unit
```
Also confirm which CUs the two e2e tests touch:
`grep -n "register\|log in\|log out\|upload\|completed\|delete" frontend/tests/e2e/full-flow.spec.ts`
and skim `backend/tests/test_end_to_end.py`.

- [ ] **Step 3: Write the matrix**

Append `## 7.3 Verificación de requisitos funcionales` with an intro sentence (the matrix traces
each caso de uso del §4 a la evidencia de que funciona) and a table whose cells are **only** files
confirmed in Step 2. Base it on spec §3's draft matrix but correct every cell against the grep
output. After the table, one short paragraph: **todos los CU tienen cobertura automatizada**; la
única laguna visible es que la prueba e2e de navegador no comprueba la vista de historial (CU-6)
como paso propio —sólo lo cubren pruebas unitarias y el uso manual—; se señala, no se oculta.

- [ ] **Step 4: Verify every filename in the table exists**

Run: `for f in $(grep -oE '[a-z_-]+\.(py|tsx?|ts)' memoria/07-evaluacion.md | sort -u); do find backend/tests cv-service/tests frontend/tests -name "$f" | grep -q . && echo "OK $f" || echo "MISSING $f"; done`
Expected: every line `OK`. Fix any `MISSING`.

- [ ] **Step 5: Render check + commit**

```bash
cd memoria && ./build-pdf.sh && echo OK && cd ..
git add memoria/07-evaluacion.md
git commit -m "docs(memoria): draft cap. 7 verificación de requisitos funcionales"
```

---

### Task 4: §7.4 Verificación de requisitos no funcionales

**Files:**
- Modify: `memoria/07-evaluacion.md` (append `## 7.4`)

**Interfaces:**
- Consumes: `memoria/07-evaluacion.md` from Task 3 (ends after §7.3).
- Produces: `## 7.4 Verificación de requisitos no funcionales` (RNF-1…RNF-7, prose or compact
  table). Task 5 appends `## 7.5`.

- [ ] **Step 1: Pull the benchmark numbers verbatim from §4**

Run: `sed -n '/### 4\.2\.2 RNF-2/,/### 4\.2\.4/p' memoria/04-requisitos.md`

Record the exact figures for RNF-2 (media, mín., máx., relación vs. duración, extrapolación,
SLA propuesto) and RNF-3 (relación por nivel de concurrencia, máx., objetivo propuesto). §7.4
quotes these **exactly** — no rounding, no rephrasing of the numbers.

- [ ] **Step 2: Verify the RNF-5 security tests exist**

Run: `grep -rln "sign_payload\|verify_signature\|HMAC\|X-API-Key\|hash_refresh_token\|revoke" backend/tests`
Expected: `test_signing.py` (both directions), `test_auth.py` (bulk revoke on reuse),
`test_cv_client.py` / `test_webhook.py` (`X-API-Key`). Use only confirmed files.

- [ ] **Step 3: Verify the RNF-7 contrast-work reference**

Run: `ls docs/superpowers/specs/2026-08-25-frontend-redesign-design.md` and
`grep -n "contrast\|contraste\|WCAG\|AA\|luminance\|luminancia" docs/superpowers/specs/2026-08-25-frontend-redesign-design.md | head`
Expected: the spec exists and documents relative-luminance contrast math for AA. §7.4 cites this
path. State plainly that no Lighthouse/axe run or screen-reader pass was done.

- [ ] **Step 4: Write §7.4**

Append per spec §4 — one bullet or table row per RNF-1…RNF-7 with `Cómo se verificó` and
`Resultado`. Key points that must appear verbatim in spirit:
- RNF-4: rule-based, **sin métrica de accuracy**; el objetivo de §4 **queda sin cuantificar** — no
  se construyó el conjunto de referencia; la evaluación cualitativa disponible es §7.5.
- RNF-6: en producción sobre el fallback gratuito de GCP, **sin SLA medido** (no hay
  monitorización de uptime).
- Caveat transversal: los benchmarks son de una única máquina de 16 núcleos, no del destino real
  (2 OCPU compartidos) — las cifras no se trasladan directamente (ya dicho en §4).

- [ ] **Step 5: Cross-check the numbers match §4 exactly**

Run: `grep -oE '1[24]\.[0-9] ?s|0\.9[0-9]×|<90 ?s|14\.9 ?s|1\.0[0-6]×' memoria/07-evaluacion.md memoria/04-requisitos.md`
Expected: the figures that appear in both files are identical strings. Fix any drift in
`07-evaluacion.md` (never edit `04-requisitos.md` here).

- [ ] **Step 6: Render check + commit**

```bash
cd memoria && ./build-pdf.sh && echo OK && cd ..
git add memoria/07-evaluacion.md
git commit -m "docs(memoria): draft cap. 7 verificación de requisitos no funcionales"
```

---

### Task 5: §7.5 Evaluación del pipeline sobre vídeo real

**Files:**
- Modify: `memoria/07-evaluacion.md` (append `## 7.5` with `### 7.5.1`–`### 7.5.4`)

**Interfaces:**
- Consumes: `memoria/07-evaluacion.md` from Task 4 (ends after §7.4).
- Produces: `## 7.5 Evaluación del pipeline sobre vídeo real` with four subsections. Task 6
  appends `## 7.6`.

**IMPORTANT — provenance:** the findings in this section come from project-session records and the
two Alejandro message docs, not fully from the repo. Verify every claim that *can* be verified
against a commit or doc (below), write the rest plainly, and **leave a review note for the user**:
after this task, the human confirms §7.5 against their own memory of the test runs before merge.

- [ ] **Step 1: Verify the codec-bug story**

Run: `git show --stat eeae94a | head -20` and
`git log --oneline | grep -iE 'codec|mp4v|avc1|h\.?264|MPEG-4'`

Expected: commit `eeae94a` changes `cv-service/pipeline.py` to encode the annotated video as H.264
(`avc1`) instead of MPEG-4 Part 2. This corroborates §7.5.2. (§6.1.5 also documents it.)

- [ ] **Step 2: Verify the scoring-curve history**

Run: `git log --oneline | grep -iE 'depth|GOOD_DEPTH|score' | head` and
`grep -n "GOOD_DEPTH_ANGLE_DEG\|GOOD_DEPTH_MIN\|GOOD_DEPTH_MAX\|aefbc6f" memoria/06-implementacion.md cv-service/GLOSARIO.md`

Expected: the two-sided `GOOD_DEPTH_MIN`/`GOOD_DEPTH_MAX` band was collapsed to a single
`GOOD_DEPTH_ANGLE_DEG` threshold (commit around `aefbc6f`), already documented in §6.1.4. §7.5.1
frames the low-score-on-a-clean-squat observation as *what surfaced that change*.

- [ ] **Step 3: Verify the front-view findings are in the Alejandro follow-up doc**

Run: `grep -n "frontal\|front-view\|junk\|espuria\|5\.1\|plausibil\|duración mínima\|setup\|colocación\|walk" docs/2026-08-20-alejandro-cv-form-error-detection-followup-message.md docs/2026-08-11-alejandro-cv-form-error-detection-message.md`

Expected: at least the forward-lean direction-agnostic issue and the impossible-depth /
plausibility-gate points appear in the 2026-08-20 follow-up. Any §7.5.3 point **not** found in
either doc gets written plainly but flagged in the Step 6 review note as "session-record only,
confirm".

- [ ] **Step 4: Verify the work-split attribution**

Run: `grep -n "Alejandro\|Datos/IA\|reparto\|split" memoria/03-planificacion.md`
Expected: §3.2 documents that Alejandro owns cv-service detection quality. §7.5 attributes the
four failure modes to his domain, citing `§3`.

- [ ] **Step 5: Write §7.5**

Append `## 7.5` with `### 7.5.1 El vídeo de referencia (squat.mp4)`, `### 7.5.2 El bug de códec
(sólo visible en navegador real)`, `### 7.5.3 Vídeo de cámara frontal (2026-08-27)`, `### 7.5.4
Alcance de esta evaluación`, following spec §5's content. In §7.5.1 add the one-sentence note that
`squat.mp4` is a watermarked stock clip, only fit for testing, not for the §5 figures (which use
the user's own clip). §7.5.4 states plainly: **N ≈ 3 vídeos, sin verdad-terreno, exploratoria**;
sirve para caracterizar modos de fallo, no para dar una cifra de fiabilidad.

- [ ] **Step 6: Write the user review note**

Append to the task's report (not the chapter) a bullet list of every §7.5 sentence that rests on
session records rather than a verified commit/doc, so the user can confirm each. At minimum: the
exact rep counts (6 / 15+5), the "min_knee_angle_deg 5.1 scored 100" detail, the angle ranges
(39–44°, 78–94°), and the "25s to process / downscaled to 720p" mechanics if included.

- [ ] **Step 7: Render check + commit**

```bash
cd memoria && ./build-pdf.sh && echo OK && cd ..
git add memoria/07-evaluacion.md
git commit -m "docs(memoria): draft cap. 7 evaluación del pipeline sobre vídeo real"
```

---

### Task 6: §7.6 Limitaciones + whole-chapter consistency pass

**Files:**
- Modify: `memoria/07-evaluacion.md` (append `## 7.6`; small edits elsewhere in the file for
  consistency)

**Interfaces:**
- Consumes: `memoria/07-evaluacion.md` from Task 5 (ends after §7.5).
- Produces: `## 7.6 Limitaciones y amenazas a la validez` (bulleted) and a fully
  internally-consistent chapter. Task 7 does the render/heading audit.

- [ ] **Step 1: Write §7.6**

Append `## 7.6 Limitaciones y amenazas a la validez` as a bulleted list per spec §6 — each item is
`limitación → consecuencia`, cross-referencing §7.2/§7.4/§7.5. Include all seven bullets from
spec §6 (no labeled dataset; single fixture video; single-machine benchmark; CI runs no tests;
exploratory CV eval; a11y reasoned not audited; no production monitoring). Closing sentence: estas
limitaciones son coherentes con el alcance (TFG de dos personas, MVP congelado, despliegue
gratuito) y se recogen explícitamente en lugar de presentar la evaluación como más completa de lo
que es; varias alimentan §10 (Conclusiones).

- [ ] **Step 2: Consistency sweep**

Run: `grep -nE '\b(128|36|73|237|225|61)\b' memoria/07-evaluacion.md`
Expected: only `128`, `36`, `73`, `237` appear as test counts; **no `225` or `61`** (stale numbers
from earlier spec drafts). Fix any.

Run: `grep -nE 'CU-[1-7]|RNF-[1-7]' memoria/07-evaluacion.md` and confirm every CU/RNF referenced
matches a real heading in `memoria/04-requisitos.md` (`grep -nE '^### 4\.[12]\.' memoria/04-requisitos.md`).

Run: `grep -n '§[0-9]' memoria/07-evaluacion.md` and confirm each `§N.M` target exists (§3.2, §4,
§5, §6.1, §6.1.4, §6.1.5, §6.1.6, §10 are the expected referents).

- [ ] **Step 3: Check for a blockquote-as-body-text mistake**

Run: `grep -nE '^>' memoria/07-evaluacion.md`
Expected: **no output** — the provenance note is an HTML comment, not a `>` blockquote (Ch.3
review finding).

- [ ] **Step 4: Commit**

```bash
git add memoria/07-evaluacion.md
git commit -m "docs(memoria): cap. 7 limitaciones y pasada de consistencia"
```

---

### Task 7: PDF render audit + numbered-heading check

**Files:**
- Modify: `memoria/07-evaluacion.md` (only if the render surfaces a problem)

**Interfaces:**
- Consumes: the complete `memoria/07-evaluacion.md` from Task 6.
- Produces: a chapter that builds cleanly through `memoria/build-pdf.sh` with correctly-numbered
  headings and no table overflow, ready for the SDD whole-branch review.

- [ ] **Step 1: Full heading audit**

Run: `grep -nE '^#{1,4} ' memoria/07-evaluacion.md`
Expected: `# 7. Evaluación`, then `## 7.1` … `## 7.6` in order, `### 7.2.1`–`### 7.2.4`,
`### 7.5.1`–`### 7.5.4`. No unnumbered `##`/`###`. No gaps or duplicates in the numbering.

- [ ] **Step 2: Build the full memoria PDF**

Run: `cd memoria && ./build-pdf.sh`
Expected: `Wrote .../memoria.pdf`, no `ERROR`, no `missing character` / `could not represent` line
in the output.

- [ ] **Step 3: Eyeball Ch.7's pages**

Run: `pdfinfo memoria/memoria.pdf | grep Pages`, then render the Ch.7 range to PNG
(`pdftoppm -png -r 90 -f <first> -l <last> memoria/memoria.pdf /tmp/ch7`) and open a couple.
Expected: the CU traceability table (§7.3) and any RNF table (§7.4) fit the page width — no row
runs off the right margin. If a table overflows, shorten the cell contents (use bare file names,
drop `.py`/`.tsx` where unambiguous, or split a wide column) — do **not** change the facts.

- [ ] **Step 4: Commit (only if Step 3 required an edit)**

```bash
git add memoria/07-evaluacion.md
git commit -m "docs(memoria): cap. 7 ajuste de tablas para el PDF"
```

- [ ] **Step 5: Report ready for review**

State: Ch.7 complete, N pages, builds clean, all counts verified against live suite runs, §7.5
review note handed to the user. Ready for the SDD whole-branch review (opus), which should pay
specific attention to §7.5 (other track's domain) and every traceability-matrix cell.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- spec §1 (§7.1) → Task 1 ✓
- spec §2 (§7.2, incl. CI) → Task 2 ✓
- spec §3 (§7.3 matrix) → Task 3 ✓
- spec §4 (§7.4 RNF) → Task 4 ✓
- spec §5 (§7.5 real video) → Task 5 ✓ (+ provenance review note, Step 6)
- spec §6 (§7.6 limitations) → Task 6 ✓
- spec §7 (tables, no Mermaid/LaTeX) → Global Constraints + Task 7 Step 3 ✓
- spec §9 (factual-accuracy verification, benchmark single-source, §7.5 user check, opus review) →
  each task's verify steps + Task 7 Step 5 ✓

**Placeholder scan:** `<HASH>` / `<commit>` / `<file>` / `<first>`/`<last>` are fill-at-write-time
tokens with an explicit command to resolve them, not vague instructions. No "TBD"/"add error
handling"/"write tests for the above". Every prose block the engineer must produce is either given
verbatim (Task 1) or pinned to spec sections with the exact points that must appear (Tasks 2–6).

**Type/name consistency:** file name `memoria/07-evaluacion.md` throughout; test counts
128 / 36 / 73 / 237 consistent across Tasks 2, 6; heading scheme `## 7.N` / `### 7.N.M` consistent
across Tasks 1–7; `eeae94a` / `aefbc6f` commit hashes match spec §5 and Ch.6.

---

## Execution Handoff

Plan complete and saved. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks.
2. **Inline Execution** — batch execution in this session with checkpoints.
