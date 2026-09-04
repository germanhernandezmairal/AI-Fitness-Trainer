# Design: Memoria — Chapter 9 (Legislación y protección de datos)

**Date:** 2026-09-04
**Author:** Fullstack role (compiled with Claude)
**Status:** DRAFT (pending user review)
**Related:** `memoria-ada-outline.md` §9 (scaffolding this chapter expands);
`memoria/04-requisitos.md` (CU-1…CU-7, RNF-1…RNF-7 — this chapter cites CU-7's erasure flow and
adds the account-level counterpart), `memoria/06-implementacion.md` (retention purge job),
`memoria/07-evaluacion.md` (sets the per-chapter-spec, file-location, Spanish-language,
numbered-heading, and "cite real code/commits" precedent this chapter follows);
`docs/superpowers/specs/2026-09-02-privacy-compliance-design.md` and
`docs/superpowers/plans/2026-09-02-privacy-compliance.md` (the code this chapter documents — consent
at registration + account-level erasure, built and merged 2026-09-02/2026-09-04, commits
`2f7375d`…`ff3ab7f`); the real source: `backend/app/models/user.py`, `backend/app/models/attempt.py`,
`backend/app/services/auth.py`, `backend/app/services/attempts.py`, `backend/app/services/users.py`,
`backend/app/services/jobs.py`, `backend/app/config.py`, `cv-service/pipeline.py`,
`frontend/src/app/privacy/page.tsx`, `frontend/src/app/register/page.tsx`,
`frontend/src/components/app-shell.tsx`, `deploy/Caddyfile`.

---

## 0. Context and goal

Same per-chapter approach as Ch.3–7: the memoria's 12 chapters are largely independent, so each is
its own sub-project (brainstorm → spec → plan → SDD). This design covers only **Chapter 9
(Legislación y protección de datos)**.

Per `memoria-ada-outline.md` §9, flagged **high priority** because the app processes video of
people's bodies: applicable law, lawful basis and consent, data minimization, retention/deletion,
encryption in transit and at rest, user rights (access, erasure), and whether pose keypoints
qualify as biometric data.

**This chapter is sub-project 2 of a 2-part unit.** Scoping it (2026-09-02) surfaced two real code
gaps — no explicit consent, no account-level erasure — and the user chose to fix them as real code
*before* writing the chapter, so the chapter can cite a real consent flow and a real erasure
endpoint instead of describing a gap. Sub-project 1 (the code) shipped and merged to `main` this
session (`ff3ab7f`). This design covers only the chapter that documents it.

**Three decisions made with the user during brainstorming (2026-09-04), before this doc was
written:**

1. **Legal depth: real citations, TFG-appropriate.** Cite actual GDPR articles (Art. 6, Art. 9,
   Art. 5(1)(e), Art. 17, Art. 15–21) and LOPDGDD only where it adds something GDPR doesn't already
   say — matching the rigor Ch.4/Ch.7 gave functional/non-functional requirements. Grounded,
   verifiable reasoning, not a formal legal opinion.
2. **`Attempt.consent_at` (backend/app/models/attempt.py:35, auto-set at
   `backend/app/services/attempts.py:80` on every upload) is documented as processing bookkeeping,
   not a second consent gate.** The real consent decision is the one-time account-level checkbox
   (`User.privacy_consent_at`, `backend/app/models/user.py:27`). §9.3 states this precisely — it
   must never read as "the user consents again per upload," because that isn't what the field does
   or what the design intended.
3. **Biometric-data conclusion (outline's explicit question): likely NOT Art. 9 biometric data, but
   still special-category-adjacent.** GDPR Art. 4(14) defines biometric data as data from specific
   technical processing used for **unique identification** — this pipeline never identifies anyone
   from body shape, and raw pose keypoints are computed per-frame in memory
   (`cv-service/pipeline.py:261-282`) but never persisted; only derived joint angles, scores, and rep
   segments survive in the returned/stored result (`cv-service/pipeline.py:302-307`). But the video
   itself (a person's body, exercising) and the derived technique scores plausibly touch "data
   concerning health" (Art. 9) as physical/exercise-performance data — so §9.2/§9.3 argue the app
   should get special-category-level care even though it isn't textbook biometric data. Honest,
   argued, not overclaiming in either direction.

**Structure decided with the user: eight sections** (§9.1–§9.8, below), approved as a whole during
brainstorming.

The chapter is written **in Spanish**, numbered headings (`## 9.1`, `### 9.2.1` where needed), new
file `memoria/09-legislacion.md`, `NN-nombre.md` pattern. `memoria-ada-outline.md` stays untouched.

---

## 1. Section 9.1 — Marco legal aplicable

Short framing section (~150–200 words). Points to make:

- **GDPR (Reglamento UE 2016/679)** applies: the project is built and (for the free-tier MVP)
  operated from Spain/the EU, and even a demo/academic deployment that could process an EU
  resident's personal data falls under it by virtue of establishment (Art. 3(1)) — no need to argue
  extraterritorial reach.
- **LOPDGDD (Ley Orgánica 3/2018)** applies alongside GDPR as Spain's implementing law — cited only
  where it adds something GDPR's text doesn't already say (e.g., Spanish specifics on the age of
  consent, or on the exercise of rights) — not restated wholesale.
- **Framing for a TFG, not a commercial product:** this is an academic project with a frozen,
  free-tier MVP (see `project_aws_deployment_constraints` project state) — the chapter reasons about
  what the *code and its data flows* do and don't satisfy, not about a company's formal compliance
  program (no DPO, no registered treatment activities record — named as scope, not hidden, and
  revisited in §9.8).

---

## 2. Section 9.2 — Categorías de datos tratados

A table, then the biometric-data argument (decision 3 above), stated in full here since this is
where the outline's explicit question lives.

| Dato | Dónde vive | Naturaleza |
|---|---|---|
| Email + hash de contraseña | `User.email`, `User.password_hash` | Identificación directa |
| Vídeo original subido | Almacenamiento local, referenciado por `Attempt.original_video_ref` | Imagen de una persona haciendo ejercicio — dato personal, potencialmente "datos relativos a la salud" (Art. 9) por su naturaleza de rendimiento físico |
| Vídeo anotado | Almacenamiento local / CV-service, `Attempt.annotated_video_url` | Igual que el original, con overlay de esqueleto MediaPipe dibujado sobre el vídeo — no un archivo separado de coordenadas |
| Puntos de referencia de pose (*pose landmarks*) | Nunca persistidos — sólo en memoria durante `analizar_video` (`cv-service/pipeline.py:261-282`) | Ver argumento de biometría abajo |
| Ángulos articulares, puntuación, repeticiones | `Attempt.result` (JSONB) | Dato derivado, no biométrico bajo Art. 4(14) — no identifica a nadie |
| Tokens de refresco (hash) | `RefreshToken.token_hash` | No es dato personal per se (es un secreto de sesión), pero vinculado a un usuario — se elimina en cascada al borrar la cuenta |

**Argumento de biometría (Art. 4(14) GDPR):** biometric data requires processing "resulting in
unique identification" from physical/physiological/behavioural characteristics. This pipeline's
`pose_landmarks` are used only to compute joint angles for *that single video's* technique feedback
— never stored, never compared across users or sessions, never used to recognize or distinguish one
person from another. **Conclusion: not Art. 9 biometric data.** But the uploaded video shows a
person's body performing a physical activity, and the derived scores are, in substance, an
assessment of physical performance — close enough to "datos relativos a la salud" that the design
already treats it with special-category-level care (explicit consent, no third-party sharing,
short retention) without needing Art. 9's stricter machinery to justify doing so.

---

## 3. Section 9.3 — Base de legitimación y consentimiento

- **Base legal: consentimiento explícito (Art. 6(1)(a)), reforzado a nivel de sensibilidad conforme
  a Art. 9(2)(a)** dado el argumento de §9.2, aunque el dato no se clasifique formalmente como
  biométrico.
- **Cómo se implementa (código real, citado):** un checkbox de consentimiento obligatorio en el
  registro (`frontend/src/app/register/page.tsx`, enlazando a `/privacy`), aplicado en el backend —
  `POST /v1/auth/register` devuelve **422** sin `consent: true`
  (`backend/app/services/auth.py:38-48`, excepción `ConsentRequired`, capturada en
  `backend/app/api/auth.py:30`). El consentimiento se registra una sola vez, como marca de tiempo
  real: `User.privacy_consent_at` (`backend/app/models/user.py:27`, `NOT NULL`, sin
  `server_default` salvo en la migración de backfill — ver §9.8).
- **Precisión sobre `Attempt.consent_at`** (decisión 2 de brainstorming, redactada aquí en su forma
  final): este campo (`backend/app/models/attempt.py:35`) se fija automáticamente en cada subida
  (`backend/app/services/attempts.py:80`) — es un **registro de cuándo se procesó cada análisis**,
  no una segunda puerta de consentimiento. El consentimiento real es la casilla única del registro;
  este campo no debe leerse como "el usuario vuelve a consentir en cada subida", porque no lo hace.
- **Consentimiento de cuentas preexistentes a la migración (nota honesta, ampliada en §9.8):** la
  migración `0003_privacy_consent.py` rellena `privacy_consent_at` con la fecha de la migración para
  filas existentes — una marca de tiempo real, pero no un evento de consentimiento genuino. Se
  disclosea aquí, no se oculta.

---

## 4. Section 9.4 — Minimización de datos

Short section (~150 words), citing what is deliberately *not* collected or built:

- No se persisten los *pose landmarks* crudos (§9.2) — sólo el resultado derivado.
- No hay exportación de datos ni edición de perfil (cambio de email) — decisión de alcance ya tomada
  en el diseño de privacidad (`docs/superpowers/specs/2026-09-02-privacy-compliance-design.md` §0,
  §5), no un olvido.
- No se comparte con terceros: el único servicio externo que toca el vídeo es el propio cv-service
  del proyecto (auth por `X-API-Key`, nunca expuesta al navegador — `backend/app/services/cv_client.py`).
- El identificador de usuario en el cv-service es el `cv_job_id`, no el email ni ningún dato
  personal directo.

---

## 5. Section 9.5 — Conservación y eliminación

- **Retención automática (Art. 5(1)(e), minimización temporal):** `backend/app/config.py:30`,
  `retention_days: int = 30` — cada `Attempt` se crea con `expires_at = ahora + 30 días`
  (`backend/app/services/attempts.py`), y el trabajo en segundo plano
  `purge_expired_attempts` (`backend/app/services/jobs.py:55`) los elimina automáticamente al
  vencer (ya evaluado en `memoria/06-implementacion.md` y `memoria/07-evaluacion.md` §7.2.1 —
  §9 cita, no re-explica el mecanismo del job).
- **Derecho de supresión, dos niveles (Art. 17):**
  1. **Por análisis individual:** `DELETE /v1/attempts/{id}` (`delete_attempt`,
     `backend/app/services/attempts.py:145`) — borra el vídeo del almacenamiento, el job del
     cv-service, y la fila, en ese orden, antes de confirmar.
  2. **De la cuenta completa (nuevo, esta sub-fase):** `DELETE /v1/users/me` (`delete_account`,
     `backend/app/services/users.py:11`) — recorre cada intento del usuario aplicando la misma
     limpieza externa (almacenamiento + cv-service) antes de borrar la fila de `User`, porque el
     `ON DELETE CASCADE` de Postgres sólo elimina filas, nunca el archivo de vídeo en disco ni el
     job del cv-service. Si el cv-service no puede confirmar el borrado de un job, la operación
     devuelve **502** y no borra nada — ninguna cuenta se reporta como eliminada sin estarlo
     realmente (`backend/app/api/users.py`).
  3. Ambos accesibles desde la interfaz real: el borrado de intento desde el historial, el borrado
     de cuenta desde el encabezado (`frontend/src/components/app-shell.tsx`,
     confirmación de tipo "escribe DELETE").

---

## 6. Section 9.6 — Seguridad

- **Cifrado en tránsito:** real. `deploy/Caddyfile` sirve el backend detrás de Caddy con HTTPS
  automático (Let's Encrypt) sobre el dominio de producción; el frontend en Vercel sirve HTTPS por
  defecto. Ya documentado como parte del despliegue (`project_aws_deployment_constraints`) — §9 lo
  cita como el hecho de seguridad relevante para protección de datos, no lo re-explica.
- **Cifrado en reposo: limitación honesta, no una función construida.** `LocalFilesystemStorage`
  (`backend/app/services/storage.py`) escribe los vídeos como archivos planos en disco — el cifrado
  en reposo depende exclusivamente de lo que la plataforma subyacente (el disco de la VM de GCP)
  ofrezca por defecto, no de una capa de cifrado de aplicación. Postgres, igual: sin
  `pgcrypto` ni cifrado a nivel de columna. Esto se nombra explícitamente como limitación (§9.8), no
  se implica cifrado que no existe.

---

## 7. Section 9.7 — Derechos de los interesados

Per-right table or short prose, Art. 15–21 GDPR, each row: right, implemented?, evidence/citation.

| Derecho | Implementado | Evidencia |
|---|---|---|
| Acceso (Art. 15) | Parcial | El usuario ve sus propios datos a través de la propia interfaz (historial, resultado de cada análisis) — no hay una exportación formal de "descarga tus datos" |
| Rectificación (Art. 16) | No | El email/contraseña no son editables tras el registro — gap explícito, fuera de alcance por decisión de diseño (`2026-09-02-privacy-compliance-design.md` §0) |
| Supresión / "derecho al olvido" (Art. 17) | Sí | §9.5 — dos niveles, real |
| Limitación del tratamiento (Art. 18) | No aplica en la práctica | No hay tratamiento continuado más allá del análisis puntual y su retención de 30 días |
| Portabilidad (Art. 20) | No | Sin exportación — mismo gap que Acceso, mismo origen |
| Oposición (Art. 21) | No aplica | La base es consentimiento (Art. 6(1)(a)), no interés legítimo — la vía de ejercicio equivalente es retirar el consentimiento borrando la cuenta (Art. 17) |

Short closing prose: el derecho mejor cubierto es la supresión (la prioridad correcta dado que el
outline marca este capítulo como de alto riesgo); acceso/rectificación/portabilidad quedan como
gaps explícitos y coherentes con el alcance de un TFG, no como omisiones descubiertas ahora.

---

## 8. Section 9.8 — Limitaciones

Bulleted, honest, cross-referencing earlier sections — same posture as Ch.7 §7.6:

- **Sin exportación ni portabilidad de datos** (§9.7) — el usuario puede eliminar pero no descargar
  sus datos.
- **Sin edición de perfil** (§9.7) — email/contraseña fijos tras el registro.
- **Cifrado en reposo dependiente de la plataforma, no de la aplicación** (§9.6).
- **Consentimiento retroactivo en cuentas preexistentes a la migración** (§9.3) — un valor real de
  `privacy_consent_at` pero no un evento de consentimiento genuino; se disclosea aquí en vez de
  presentarse como si todas las cuentas hubieran consentido activamente.
- **Sin DPO ni registro formal de actividades de tratamiento** (§9.1) — apropiado para el alcance
  académico de este TFG, no para un despliegue comercial.
- **El panel de confirmación de borrado de cuenta no es un diálogo accesible** (`app-shell.tsx`,
  hallazgo de la revisión final de la sub-fase de código): sin `role="dialog"`, sin gestión de foco,
  sin cierre por Escape — aceptable para este MVP, mencionado aquí porque toca directamente al
  ejercicio del derecho de supresión, no sólo a la accesibilidad general (RNF-7, ya tratada en
  Ch.7).

Closing sentence, same posture as Ch.7: estas limitaciones son coherentes con el alcance (TFG de dos
personas, MVP congelado) y se recogen aquí explícitamente en lugar de presentar el cumplimiento como
más completo de lo que es.

---

## 9. Diagrams and tables

- **No Mermaid, no LaTeX.**
- **3 Markdown tables:** categorías de datos (§9.2), derechos de los interesados (§9.7); a table is
  optional for §9.5's two-level erasure summary if prose alone doesn't read cleanly — implementer's
  call, prose is the default.
- No source-code blocks — this chapter cites file:line, it doesn't reproduce code (matches Ch.7's
  own rule).

---

## 10. Out of scope (explicit)

- Re-explaining the privacy-compliance feature's implementation mechanics — that's what
  `docs/superpowers/specs/2026-09-02-privacy-compliance-design.md` and the code itself are for; §9
  cites and interprets legally, does not re-narrate the build.
- Costs (§8), overall project conclusions (§10 of the memoria) — separate chapters.
- Building anything new: no data export feature, no profile-editing feature, no at-rest encryption.
  This chapter documents what exists and discloses what doesn't, per the same "retrospective, not a
  new build" posture Ch.7 took for its own domain.
- Formal legal opinion or compliance certification — this is reasoned, cited, TFG-level analysis,
  not a law firm's memo.

---

## 11. Testing / verification approach

Documentation chapter — "testing" means factual accuracy, same bar as Ch.3–7:

- Every file:line citation re-checked against current source immediately before writing (all
  citations in this spec were pulled from the real files during brainstorming, not recalled from
  memory — re-verify once more at write time since the merge landed the same session).
- Every GDPR/LOPDGDD article citation checked against the article's actual text (not just its
  common name) before the claim is written — a Spanish-language TFG reviewer may check these.
- The biometric-data argument (§9.2) is a substantive claim — write it so it visibly argues from
  Art. 4(14)'s actual definition, not just asserts a conclusion.
- Cross-check §9.5/§9.7 against `docs/superpowers/specs/2026-09-02-privacy-compliance-design.md`'s
  own out-of-scope list (§0/§5) so this chapter's "not implemented" claims match what that spec
  already decided deliberately, rather than reading as newly-discovered gaps.
- Whole-chapter review (opus, matching Ch.3–7's final-review step) before merge — specific attention
  to every legal citation (article number matches the claim) and every code citation (file:line
  still says what the chapter claims).

---

## 12. Open questions

None — the three real decisions (legal depth; `Attempt.consent_at` framing; biometric-data
conclusion) and the eight-section structure were resolved with the user during brainstorming
(2026-09-04) before this doc was written.
