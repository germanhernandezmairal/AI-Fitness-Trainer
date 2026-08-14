# Design: Memoria — Chapter 3 (Planificación)

**Date:** 2026-08-14
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED (2026-08-14)
**Related:** `memoria-ada-outline.md` §3 (scaffolding this chapter expands), `memoria/04-requisitos.md`
(the one existing memoria chapter, sets the file-location and per-chapter-spec precedent), `git log`
on `main` and `origin/cv-pipeline` (the chapter's actual source data).

---

## 0. Context and goal

Same per-chapter approach as Chapter 4: the memoria's 12 chapters are largely independent, so each
is its own sub-project — spec it, write it, move on. This design covers only **Chapter 3
(Planificación)**: a Gantt chart plus phase narrative of the project's actual development timeline.

**Scope: retrospective only.** Covers 2026-07-23 (initial commit) through 2026-08-14 (today,
`main` at `667c47d`). Explicitly does **not** project forward into not-yet-started work (AWS
deployment, remaining memoria chapters, cv-service accuracy work) — those don't have real dates
yet and forcing them into the chart now would mean revising it later. If a forward-looking view is
ever wanted, that's a separate addition to this chapter, not part of this pass.

The chapter is written **in Spanish**, matching Chapter 4 and the course. New file
`memoria/03-planificacion.md`, following the `NN-nombre.md` pattern Chapter 4 established. Not
edited in place inside `memoria-ada-outline.md`, which stays the untouched planning skeleton.

## 1. Data source and phase breakdown

Grounded directly in `git log` on `main` (this repo) and `origin/cv-pipeline` (Alejandro's branch,
orphan history, grafted into `main` at `3c6702f` on 2026-08-04) — not reconstructed from memory.
Two parallel tracks, per the outline's own framing (§3's existing note: "Data/AI (Alejandro)" vs.
"Fullstack (you)"), syncing at the API contract boundary.

| # | Fase | Pista | Fechas | Hitos clave |
|---|---|---|---|---|
| 1 | Concepción y planificación | Fullstack | 07-23 → 07-27 | Commit inicial, esbozo de memoria, investigación de mercado, diseño del contrato API backend↔CV |
| 2 | API de intentos (backend) | Fullstack | 07-28 → 08-03 | Plan TDD de 14 tareas: modelos, auth JWT dev, storage, validación de subida, firma HMAC, cliente CV, endpoints CRUD+historial, webhook, purga/reconciliación, CV falso + test e2e |
| 3 | MVP del pipeline de visión | Datos/IA (Alejandro) | 07-27 → 08-04 | Detección de pose, cálculo de ángulos, scoring, servicio FastAPI real; injertado en `main` el 08-04 |
| 4 | Autenticación real | Fullstack | 08-04 | Registro/login/refresh/logout, tokens de refresco opacos hasheados |
| 5 | Frontend v1 | Fullstack | 08-04 → 08-07 | Next.js, flujo completo subida→resultado, historial, e2e con Playwright; PR #2 fusionado |
| 6 | Consolidación de contrato y memoria Cap. 4 | Ambas | 08-07 → 08-11 | Acceso local con frontend, corrección de códec de vídeo, capítulo de Requisitos escrito y fusionado |
| 7 | Pulido de diseño del frontend | Fullstack | 08-12 | Retema, cabecera `AppShell`, escala tipográfica, tarjetas de resultado |
| 8 | Seguimiento del pulido de frontend | Fullstack | 08-13 → 08-14 | Cierre de hallazgos diferidos de la revisión final (incl. episodio de reconciliación con automatización de Gas Town) |

**Honest note to include in the narrative, not smoothed over:** track 3 (Alejandro) is dense
07-27→08-04 (MVP shipped) and then goes quiet — a form-error-detection request was sent 08-07 and
again 08-11, still awaiting his reply as of 08-14. This is a real inter-track dependency/blocking
point, worth stating plainly as a planning-chapter fact (why a whole requirement category —
`knee_valgus`/`insufficient_depth`/`excessive_forward_lean` detection — has no committed timeline
yet), not glossed over as if both tracks ran continuously.

## 2. Gantt chart format

A Mermaid `gantt` diagram, embedded directly in `memoria/03-planificacion.md` as a ` ```mermaid `
fenced block — renders natively on GitHub and in any Mermaid-aware viewer, stays as plain
editable text (no external tool round-trip), and is easy to extend later if a forward-looking
version is ever wanted. Two `section`s, one per track, matching the table above. Dates use the
project's actual commit dates (`YYYY-MM-DD`) as phase start/end, not estimates.

## 3. Output file and structure

New file: `memoria/03-planificacion.md`, Spanish, containing:
1. Brief intro paragraph (what this chapter shows, the two-track framing — matches the outline's
   own §3 note).
2. The Mermaid Gantt chart.
3. A phase-by-phase narrative (one short paragraph per row of the table above), citing real
   commit hashes / PR numbers as evidence, not just dates.
4. The Alejandro-dependency note from §1 above, stated explicitly.

## 4. Out of scope for this chapter

- Any phase or date beyond 2026-08-14 (today) — see §0's scope decision.
- Cost/effort estimates (hours, rate) — that's Chapter 8 (Evaluación de costes), not this one.
- Any chapter other than §3.
- Reconciling other stale notes elsewhere in `memoria-ada-outline.md` — out of scope here, same as
  Chapter 4's precedent.

## 5. Testing / verification

Not applicable in the usual sense — this is a writing deliverable. "Verification" here means: every
date, commit hash, and PR reference in the written chapter is checked against actual `git log`
output at write time (this design doc's table is the source list to verify against, not treated as
already-final).
