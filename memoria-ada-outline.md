# Memoria del Proyecto — AI Fitness Trainer

> **Standard:** ADA (*Análisis y Diseño de Aplicaciones*) — structure per slide 6 of `Presentacion_TFG_2024.pdf` / `image.png`.
> **Purpose:** Working outline of the project report (*memoria*). Section titles follow the ADA standard; the notes under each are project-specific scaffolding to expand into the final report.
>
> **Note:** "ADA" here is the course *Análisis y Diseño de Aplicaciones*, **not** the accessibility act. Accessibility (WCAG) still appears — as a non-functional requirement in §4.

---

## Índice
- Chapters, figures (figuras), tables (tablas), acronyms (siglas).
- _Generate last, once section numbering is stable._

---

## 1. Introducción
General description of the project: environment, needs, expected use.

- **Problema / necesidad:** Athletes rarely have a trainer watching every rep, so form errors go uncorrected → injury risk and plateaus. Need: instant, objective technique feedback.
- **Entorno:** Amateur / semi-pro athletes and gyms.
- **Previsión de uso:** Upload or record a lift (squat, push-up, deadlift…) → receive a technique score + actionable tips → track progress over time.
- **Solución propuesta:** AI coach that detects body pose, evaluates the movement, scores it, and returns human-readable improvement tips.

---

## 2. Objetivos
Goals pursued + justification of the topic from a **formative** (learning) standpoint.

- **Objetivos del proyecto:**
  - Detect body pose (skeletal keypoints) frame by frame.
  - Evaluate technique against correct-form patterns.
  - Produce a quantitative technique score per attempt.
  - Generate specific, human-readable improvement tips.
  - User accounts with history of past attempts and progress.
- **Justificación formativa:** Combines computer vision / deep learning (pose estimation, scoring models) with full-stack web engineering, DevOps, and cloud deployment. State explicitly what *you* (Fullstack role) set out to learn: API design, containerization, AWS deployment, integrating an AI service into a production web app.

---

## 3. Planificación
Gantt chart of the project's development.

- Phases: research → MVP data pipeline → **API contract** (back end ↔ AI service) → front-end upload/results flow → auth + history → containerization → AWS deploy → testing → writing the *memoria*.
- Show the two parallel tracks that sync at the API boundary:
  - **Data/AI (Alejandro):** pose pipeline, evaluation, scoring, feedback.
  - **Fullstack (you):** web app, back end, DB, infra, deployment.
- _Insert Gantt chart figure here._

---

## 4. Requisitos del proyecto
Functional (use cases) + non-functional requirements.

### Requisitos funcionales (casos de uso)
- Upload or record a video of an exercise.
- Run pose detection and movement analysis.
- Return a numeric technique score per attempt.
- Return personalized improvement tips.
- Register / login.
- View history and progress over time.

_Write each as a use case: actor · precondition · main flow · postcondition._

### Requisitos no funcionales
- Max analysis latency per video.
- Supported video formats / resolution.
- Concurrent-user capacity.
- Model accuracy target.
- Security: authentication, encrypted storage.
- Availability.
- **Accessibility (WCAG)** of the UI.

---

## 5. Diseño
Architecture, use diagrams, class design, UI design, data persistence design.

- **Arquitectura:** Front End (React/Next.js) → Back End (FastAPI/Express) → AI Service (PyTorch) + PostgreSQL, with Redis caching heavy results. _(See diagram in `ai-fitness-trainer-concept.md`.)_
- **Diagramas de uso:** UML use-case diagram derived from §4.
- **Diseño de clases:** `User`, `Attempt`, `Exercise`, `Score`, `Feedback/Tip`, `VideoAsset`.
- **Diseño de interfaz:** Wireframes for (a) upload/record, (b) results = score + annotated feedback, (c) progress dashboard.
- **Persistencia (BD):** PostgreSQL schema — `users`, `attempts`, `results`, `history`. Document what is cached in Redis and why.

---

## 6. Implementación
Technology details and specific algorithms — **not the code itself**.

- **AI side:** pose estimation (OpenCV + PyTorch/TensorFlow keypoint extraction); joint-angle computation frame by frame; technique-comparison / scoring logic; tip-generation method.
- **App side:** REST contract between back end and AI service; FastAPI vs. Express choice + rationale; Next.js front end; Docker packaging; AWS services used.

---

## 7. Evaluación
Test-case design covering the requirements + detailed results and project evaluation.

- Design test cases that **trace back to each requirement** (e.g. "known-good squat video → score ≥ threshold").
- **AI-side evaluation:** model accuracy / validation against labeled clips.
- **App-side testing:** unit, integration, end-to-end.
- Report **actual results**, not just the plan.

---

## 8. Evaluación de costes
Personnel and material costs.

- **Personal:** estimated hours × rate for both roles.
- **Material / infraestructura:** AWS compute/GPU for inference, storage, domain, datasets, tooling.
- Optional: dev-vs-production cost breakdown.

---

## 9. Legislación y protección de datos
Applicable law + how data-protection legislation is applied. **High-priority section — the app processes video of people's bodies.**

- Likely **personal and potentially biometric** data under **GDPR / LOPDGDD** (Spain).
- Cover: lawful basis and consent; data minimization; retention/deletion of uploaded videos; encryption at rest and in transit; user rights (access, erasure).
- Flag whether pose keypoints qualify as **biometric data**.

---

## 10. Conclusiones
Assessment of the work done + contribution to personal training.

- Achieved vs. objectives (§2).
- What you'd do differently.
- **Contribution to personal/professional formation:** shipping an AI-integrated full-stack app end to end.

---

## 11. Recursos utilizados
Bibliography, software, hardware.

- **Bibliografía:** inspiration video (<https://www.youtube.com/watch?v=Ae3SPjsXETc>), pose-estimation papers/docs.
- **Software:** React/Next.js, Node/Express or FastAPI, PostgreSQL, Redis, Docker, PyTorch, TensorFlow, OpenCV, scikit-learn, AWS, Git/GitHub, VS Code.
- **Hardware:** dev machines, any GPU used for training/inference.

---

## 12. Anexos
Deployment: installation, requirements, user & maintenance documentation.

- Installation steps + system requirements.
- Run locally (Docker Compose) and on AWS.
- User documentation and maintenance guide.

---

_Source references: `ai-fitness-trainer-concept.md`, `Presentacion_TFG_2024.pdf` (slide 6), `image.png`._
