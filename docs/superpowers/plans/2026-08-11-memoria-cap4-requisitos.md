# Memoria Chapter 4 (Requisitos) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `memoria/04-requisitos.md`, the finished Chapter 4 (Requisitos) of the project's
academic report — 7 functional requirements as use cases and 7 non-functional requirement
categories (Real vs. Objetivo) — in Spanish.

**Architecture:** This is a writing deliverable, not code. Each task's "test cycle" is a
source-of-truth verification (grep/read the actual backend/cv-service code) *before* writing the
corresponding prose, and a re-check *after*, so every factual claim in the chapter is traceable to
a real file:line rather than assumed from memory. No test suite runs — "passing" means the written
prose matches the verified fact.

**Tech Stack:** Markdown. No code changes.

## Global Constraints

- Written entirely in Spanish (per the approved spec, §0).
- Use cases follow the actor · precondición · flujo principal · postcondición template (spec §1).
- Every non-functional requirement states both a "Real" value (sourced from code) and an
  "Objetivo" value where no real value exists yet — never a single unqualified claim (spec §2).
- Output file: `memoria/04-requisitos.md` (new `memoria/` directory) — `memoria-ada-outline.md`
  itself is NOT edited (spec §0, §3).
- No UML diagrams in this chapter — deferred to §5 (spec §4).

---

### Task 1: Scaffold the file and write the 7 functional requirements (use cases)

**Files:**
- Create: `memoria/04-requisitos.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `memoria/04-requisitos.md` with a `# 4. Requisitos del proyecto` H1, a
  `## Requisitos funcionales (casos de uso)` H2, and 7 use-case subsections under it. Task 2
  appends a sibling `## Requisitos no funcionales` H2 after this content.

- [ ] **Step 1: Verify the 7 backing routes still exist and match the spec's table**

Run: `grep -rhE "@router\.(get|post|delete|put|patch)" backend/app/api/*.py`

Expected output (order may vary): `POST /register`, `POST /login`, `POST /refresh`,
`POST /logout` (from `auth.py`), `POST ""` (create attempt, 202), `GET "/{attempt_id}"`,
`GET ""` (list), `GET "/{attempt_id}/video"`, `DELETE "/{attempt_id}"` (from `attempts.py`), plus
the webhook-receiving `POST "/{attempt_id}"` (204) and `POST "/dev-login"` (excluded — dev-only).
If any route is missing or renamed, update the "Fuente" line for that use case in Step 2 before
writing it.

- [ ] **Step 2: Create the file with the full functional-requirements section**

Create `memoria/04-requisitos.md`:

```markdown
# 4. Requisitos del proyecto

> Fuente: `docs/superpowers/specs/2026-08-11-memoria-cap4-requisitos-design.md` (diseño aprobado).
> Casos de uso derivados directamente del inventario de rutas en `backend/app/api/`, no de la
> lista original de `memoria-ada-outline.md` §4 (que agrupaba un paso interno del sistema —
> detección de pose — como si fuera una acción propia del usuario).

## Requisitos funcionales (casos de uso)

### CU-1: Registrarse

- **Actor:** Usuario no autenticado.
- **Precondición:** El usuario dispone de un email no registrado previamente y una contraseña.
- **Flujo principal:**
  1. El usuario introduce email y contraseña en el formulario de registro.
  2. El sistema valida el formato del email y la fortaleza de la contraseña.
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
- **Precondición:** El usuario está autenticado y dispone de un video (`.mp4` o `.mov`, ≤100MB,
  ≤60s).
- **Flujo principal:**
  1. El usuario selecciona o graba un video y lo sube desde el formulario de carga.
  2. El backend valida extensión, tamaño y duración del archivo.
  3. El backend crea el intento (estado "pendiente") y lo reenvía a cv-service.
  4. cv-service procesa el video de forma asíncrona (detección de pose, conteo de repeticiones,
     scoring) y notifica el resultado al backend mediante un webhook firmado (HMAC-SHA256).
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
     los consejos de mejora y una URL del video anotado.
  3. Si el usuario reproduce el video anotado, el frontend lo solicita a través del endpoint proxy
     autenticado — nunca directamente a cv-service.
- **Postcondición:** El usuario visualiza el score, los consejos y el video anotado de su intento,
  sin que la clave interna de cv-service llegue nunca al navegador.
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
  2. El backend elimina el intento y su video asociado en su propia base de datos.
  3. El backend solicita a cv-service la eliminación del job y sus archivos (video original y
     anotado).
- **Postcondición:** Ni el backend ni cv-service conservan datos del intento eliminado.
- **Fuente:** `DELETE /v1/attempts/{attempt_id}` (backend); `DELETE /v1/jobs/{id}` (cv-service,
  invocado internamente por el backend).
```

- [ ] **Step 3: Verify the written use cases against the route grep from Step 1**

Re-run: `grep -n "Fuente" memoria/04-requisitos.md`

Confirm each of the 7 lines names a route that actually appeared in Step 1's output. If Step 1
surfaced a route rename/removal, this is where it must already be reflected — fix now if not.

- [ ] **Step 4: Commit**

```bash
git add memoria/04-requisitos.md
git commit -m "docs(memoria): draft cap. 4 requisitos funcionales (casos de uso)"
```

---

### Task 2: Write the 7 non-functional requirement categories (Real vs. Objetivo)

**Files:**
- Modify: `memoria/04-requisitos.md` (append after Task 1's content)

**Interfaces:**
- Consumes: `memoria/04-requisitos.md` as produced by Task 1 (appends after its last line).
- Produces: the completed `memoria/04-requisitos.md`, ready for Task 3's final pass.

- [ ] **Step 1: Verify upload format/size/duration limits**

Run: `grep -n "ALLOWED_EXTENSIONS\|max_upload_bytes\|max_duration_sec" backend/app/services/validation.py backend/app/config.py`

Expected output includes: `ALLOWED_EXTENSIONS = {".mp4", ".mov"}`
(`backend/app/services/validation.py:10`), `max_upload_bytes: int = 104_857_600`
(`backend/app/config.py:27`), `max_duration_sec: int = 60` (`backend/app/config.py:28`). If the
values differ, use the actual current values in Step 4 below instead of the ones shown here.

- [ ] **Step 2: Verify security implementation (auth + webhook signing)**

Run: `ls backend/app/security/ && grep -n "class\|def " backend/app/security/signing.py`

Expected: `backend/app/security/signing.py` exists and defines an HMAC-SHA256 signing function
over `timestamp + "." + body`. Also confirm refresh-token storage is hashed, not plaintext:
`grep -n "hash" backend/app/services/auth.py`.

- [ ] **Step 3: Verify the scoring pipeline is rule-based, not a trained model**

Run: `grep -n "GOOD_DEPTH_MIN\|def score_from_angle" cv-service/pipeline.py`

Expected: a module-level threshold constant (e.g. `GOOD_DEPTH_MIN`) feeding a scoring function —
confirms there is no accuracy/precision/recall metric to report, only threshold-based rules.

- [ ] **Step 4: Append the non-functional-requirements section**

Append to `memoria/04-requisitos.md`:

```markdown

## Requisitos no funcionales

Cada categoría distingue explícitamente entre lo que el sistema **ya cumple hoy** ("Real",
verificado contra el código) y lo que queda como **objetivo** a alcanzar más adelante — nunca se
mezclan ambas cosas en una sola afirmación.

### Formatos y tamaño de video

- **Real:** extensiones permitidas `.mp4` y `.mov`
  (`backend/app/services/validation.py::ALLOWED_EXTENSIONS`); tamaño máximo 100 MB
  (`104_857_600` bytes, `backend/app/config.py`); duración máxima 60s
  (`backend/app/config.py`). cv-service aplica los mismos límites de forma independiente
  (`cv-service/main.py::MAX_FILE_SIZE_BYTES`, `MAX_DURATION_SEC`).
- **Objetivo:** — ya cumplido en ambos servicios; no queda pendiente.

### Latencia de análisis

- **Real:** el análisis es asíncrono (subida → cv-service → webhook → actualización de estado);
  no existe una medición formal de tiempo end-to-end ni un SLA declarado.
- **Objetivo:** definir un tiempo máximo razonable (p. ej. análisis completo en menos de N
  segundos para un video de 60s), a confirmar con datos reales de Alejandro sobre tiempos de
  inferencia de cv-service.

### Capacidad concurrente

- **Real:** sin pruebas de carga realizadas; cv-service procesa cada job de forma síncrona.
- **Objetivo:** declarar el número de análisis simultáneos soportado, pendiente de definir tras
  pruebas de carga.

### Precisión del modelo

- **Real:** no es un modelo de ML entrenado con métricas de accuracy/precision/recall — es un
  pipeline de reglas basado en umbrales de ángulo articular (p. ej. `GOOD_DEPTH_MIN` en
  `cv-service/pipeline.py`).
- **Objetivo:** en vez de un target de accuracy clásico, definir un objetivo de fiabilidad de
  detección (p. ej. porcentaje de repeticiones correctamente contadas sobre un set de videos de
  referencia).

### Seguridad

- **Real:** autenticación JWT (access token en memoria, refresh token opaco y hasheado en
  `localStorage`), revocación en bloque de todos los refresh tokens de un usuario ante detección
  de reuso, firma HMAC-SHA256 en los webhooks entre backend y cv-service
  (`backend/app/security/signing.py`).
- **Objetivo:** — ya cumplido; se documenta como logrado, no como pendiente.

### Disponibilidad

- **Real:** sin despliegue en AWS todavía (solo entorno local/desarrollo); sin SLA de
  disponibilidad definido.
- **Objetivo:** definir un objetivo de disponibilidad (p. ej. 99%) una vez desplegado en
  producción.

### Accesibilidad (WCAG)

- **Real:** no se ha realizado una auditoría formal de accesibilidad; el frontend usa componentes
  de shadcn/ui (basados en Radix UI, accesibles por defecto), pero esto no se ha verificado
  explícitamente contra WCAG en este proyecto.
- **Objetivo:** alcanzar conformidad WCAG 2.1 nivel AA, a confirmar con una auditoría (p. ej.
  Lighthouse o axe).
```

- [ ] **Step 5: Verify every "Real" claim in the new section against Steps 1-3's output**

Re-read the appended section and cross-check each bolded **Real:** line against the corresponding
grep output from Steps 1-3. If any value drifted (e.g. limits changed since this plan was
written), correct it now before committing.

- [ ] **Step 6: Commit**

```bash
git add memoria/04-requisitos.md
git commit -m "docs(memoria): draft cap. 4 requisitos no funcionales (real vs. objetivo)"
```

---

### Task 3: Final consistency pass

**Files:**
- Modify: `memoria/04-requisitos.md` (fixes only, if any)

**Interfaces:**
- Consumes: the complete `memoria/04-requisitos.md` from Tasks 1-2.
- Produces: final, reviewed `memoria/04-requisitos.md`.

- [ ] **Step 1: Re-read the whole file top to bottom**

Read `memoria/04-requisitos.md` in full and check against the approved spec
(`docs/superpowers/specs/2026-08-11-memoria-cap4-requisitos-design.md`):
- All 7 use cases present, each with all 4 template fields (actor, precondición, flujo principal,
  postcondición) and a "Fuente" line.
- All 7 non-functional categories present, each with both a "Real" and an "Objetivo" line (or an
  explicit "—" where already fulfilled).
- Entirely in Spanish — no leftover English scaffolding notes copied in from
  `memoria-ada-outline.md`.
- `memoria-ada-outline.md` itself untouched (`git diff --stat memoria-ada-outline.md` should be
  empty).

- [ ] **Step 2: Fix any drift found in Step 1**

Apply fixes directly to `memoria/04-requisitos.md` if Step 1 found anything (missing field,
stray English text, an unverified claim). If nothing is found, skip to Step 3.

- [ ] **Step 3: Confirm outline file was never modified**

Run: `git diff --stat memoria-ada-outline.md`

Expected: no output (file unchanged).

- [ ] **Step 4: Commit (only if Step 2 made changes)**

```bash
git add memoria/04-requisitos.md
git commit -m "docs(memoria): fix cap. 4 consistency pass"
```

If Step 2 made no changes, skip this commit — Tasks 1 and 2 already captured the finished chapter.
