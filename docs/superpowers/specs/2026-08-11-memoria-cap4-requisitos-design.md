# Design: Memoria — Chapter 4 (Requisitos)

**Date:** 2026-08-11
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED (2026-08-11)
**Related:** `memoria-ada-outline.md` §4 (scaffolding this chapter expands), `docs/superpowers/specs/2026-07-27-api-contract-design.md`, `docs/superpowers/specs/2026-08-04-real-auth-design.md`, `backend/app/api/` (route inventory this chapter is grounded in).

---

## 0. Context and goal

`memoria-ada-outline.md` is the working outline for this project's academic report (*memoria*,
ADA standard — *Análisis y Diseño de Aplicaciones*), still just scaffolding notes under each
section header. The memoria is too large to design as one project — its 12 chapters are largely
independent (architecture write-up, cost analysis, legal/GDPR, testing results, etc.) — so each
chapter is being treated as its own sub-project: spec it, write it, move to the next. This design
covers only **Chapter 4 (Requisitos)**: functional requirements as use cases, and non-functional
requirements.

The chapter is written **in Spanish**, matching the course and the section titles (the outline's
current English scaffolding notes are working notes only, not the target language). It lives as
its own file, **not** edited in place inside `memoria-ada-outline.md`, which stays the untouched
planning skeleton for all 12 chapters.

## 1. Use-case inventory (functional requirements)

The outline's original bullet list (`Upload/record video`, `Run pose detection and movement
analysis`, `Return score`, `Return tips`, `Register/login`, `View history`) conflates one system-
internal step (pose detection/analysis) with user-facing actions. Grounding directly in the real
route inventory (`backend/app/api/`) instead produces seven use cases, one user-facing action each:

| # | Caso de uso | Actor | Backed by |
|---|---|---|---|
| 1 | Registrarse | Usuario | `POST /v1/auth/register` |
| 2 | Iniciar sesión | Usuario | `POST /v1/auth/login` |
| 3 | Cerrar sesión | Usuario | `POST /v1/auth/logout` |
| 4 | Subir video de un intento | Usuario (+ Sistema/CV service, asíncrono) | `POST /v1/attempts`, webhook callback |
| 5 | Consultar resultado de un intento (score + consejos + video anotado) | Usuario | `GET /v1/attempts/{id}`, `GET /v1/attempts/{id}/video` |
| 6 | Ver historial de intentos | Usuario | `GET /v1/attempts` |
| 7 | Eliminar un intento (derecho al olvido / GDPR) | Usuario | `DELETE /v1/attempts/{id}` |

`POST /v1/auth/dev-login` is dev-only tooling (bypasses real auth for local testing) — excluded,
not a real use case.

**Template per use case** (per the outline's own instruction): actor · precondición · flujo
principal · postcondición.

## 2. Non-functional requirements — actual vs. target

Per category from the outline, each gets both a "Real" value sourced from the actual code/tests
where one exists, and a "Objetivo" (target) value where the system doesn't yet have one — these
are kept as two explicitly separate, labeled columns/subsections in the written chapter, never
blended into a single unqualified claim:

| Categoría | Real (del código) | Objetivo |
|---|---|---|
| Formatos/tamaño de video | Límites de `cv-service` (a reconfirmar contra el código actual al redactar — ~100MB/60s por [[project-backend-status]]) | — |
| Latencia de análisis | Asíncrono vía polling + reconciler, sin SLA formal medido | Definir un objetivo razonable |
| Capacidad concurrente | Sin pruebas de carga realizadas | Objetivo únicamente, declarado como gap |
| Precisión del modelo | No es ML entrenado — pipeline de reglas/umbrales (`GOOD_DEPTH_MIN`, etc.), no una métrica de accuracy clásica | Reformular como objetivo de fiabilidad de detección, no "accuracy" |
| Seguridad | JWT access + refresh opacos hasheados, revocación en bloque ante reuso, firma HMAC en webhooks | — (ya cumplido) |
| Disponibilidad | Sin despliegue AWS aún, sin SLA | Objetivo únicamente |
| Accesibilidad (WCAG) | No auditado formalmente; hereda accesibilidad base de shadcn/ui | Objetivo a confirmar |

Every "Real" value must be re-verified against the actual current code at write time, not assumed
from memory notes (this design doc's own table only records the plan for *where to look*, not
final confirmed numbers).

## 3. Output file and structure

New file: `memoria/04-requisitos.md`, Spanish, following the outline's existing two-part
structure (`Requisitos funcionales` as the 7 use cases above, `Requisitos no funcionales` as the
7 categories above). This is the first file in a new `memoria/` directory — later chapters will
follow the same `NN-nombre.md` pattern as they're picked up.

## 4. Out of scope for this chapter

- UML use-case diagrams — explicitly deferred to §5 (Diseño) per the outline's own split.
- Any chapter other than §4.
- Reconciling the outline's other stale technical notes (e.g. §5/§6 still mention Redis caching
  and an undecided FastAPI-vs-Express choice, both settled since) — out of scope here, will surface
  again when §5/§6 are picked up as their own sub-project.

## 5. Testing / verification

Not applicable in the usual sense — this is a writing deliverable. "Verification" here means: every
"Real" NFR value and every use case's `Backed by` route is checked against the actual current code
before the chapter is considered done, not left as an assumption from this design doc or from
memory.
