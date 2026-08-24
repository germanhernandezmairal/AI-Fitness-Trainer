# 5. Diseño

> Fuente: `docs/superpowers/specs/2026-08-24-memoria-cap5-diseno-design.md` (diseño aprobado).
> Arquitectura y componentes descritos según el sistema realmente implementado, no según la
> propuesta original de `memoria-ada-outline.md` §5 (que mencionaba Redis, PyTorch y Express —
> ninguno de los tres existe en el sistema real).

## Arquitectura

```mermaid
graph TB
    subgraph Cliente
        FE["Next.js Frontend<br/>(App Router)"]
    end
    subgraph "Backend (dominio público)"
        BE["FastAPI Backend<br/>(API de intentos, auth)"]
    end
    subgraph "cv-service (uso interno)"
        CV["FastAPI + MediaPipe/OpenCV<br/>(análisis de pose)"]
    end
    DB[("PostgreSQL")]
    FS[("Almacenamiento local<br/>de video")]

    FE -->|"HTTPS + JWT<br/>(access en memoria, refresh en localStorage)"| BE
    BE -->|"multipart upload + X-API-Key"| CV
    CV -->|"webhook firmado<br/>HMAC-SHA256"| BE
    BE --> DB
    BE --> FS
    FE -.->|"GET /v1/attempts/{id}/video<br/>(proxy autenticado)"| BE
```

El frontend llama al backend directamente desde el navegador — no existe una capa BFF
(*Backend-for-Frontend*) intermedia en Next.js; el token de acceso vive en memoria y el de
refresco en `localStorage` (`frontend/src/lib/api-client.ts`).

**Video anotado: proxy autenticado, nunca acceso directo.** La URL del video anotado que produce
cv-service nunca llega al navegador tal cual. El backend la reescribe a
`GET /v1/attempts/{attempt_id}/video` (`backend/app/api/attempts.py`), una ruta protegida por JWT
que descarga el video de cv-service usando la clave interna (`X-API-Key`) del backend y la
retransmite al usuario. Esta indirección existe por una razón concreta: la clave interna de
cv-service no debe llegar jamás al navegador de un usuario — si la URL original se expusiera
directamente, cualquiera con ella podría usarla para llamar a cv-service sin autenticarse como
usuario del sistema.

**Comunicación backend ↔ cv-service firmada.** Cada webhook que cv-service envía al backend al
terminar un análisis va firmado con HMAC-SHA256 sobre `timestamp + "." + body`
(`backend/app/security/signing.py`), con la firma y el timestamp en las cabeceras
`X-CV-Signature`/`X-CV-Timestamp`. El backend rechaza cualquier webhook cuya firma no coincida,
evitando que un tercero pueda falsificar el resultado de un análisis.

## Diagramas de uso

Diagrama de casos de uso derivado directamente de los 7 casos de uso funcionales del Capítulo 4
(`memoria/04-requisitos.md`) — Mermaid no tiene una notación UML de casos de uso nativa, por lo que
se usa un `flowchart` con el actor conectado a cada caso de uso, la alternativa habitual.

```mermaid
flowchart LR
    Usuario(["Usuario"])
    CU1(["CU-1: Registrarse"])
    CU2(["CU-2: Iniciar sesión"])
    CU3(["CU-3: Cerrar sesión"])
    CU4(["CU-4: Subir video de un intento"])
    CU5(["CU-5: Consultar resultado de un intento"])
    CU6(["CU-6: Ver historial de intentos"])
    CU7(["CU-7: Eliminar un intento (derecho al olvido / GDPR)"])

    Usuario --- CU1
    Usuario --- CU2
    Usuario --- CU3
    Usuario --- CU4
    Usuario --- CU5
    Usuario --- CU6
    Usuario --- CU7
```

No existe ningún actor adicional (no hay rol de administrador en el sistema real) ni ningún caso de
uso fuera de estos 7 — este diagrama visualiza los requisitos del Capítulo 4, no añade alcance
nuevo.

## Diseño de clases

```mermaid
classDiagram
    class User {
        +UUID id
        +str email
        +str? hashed_password
        +datetime created_at
    }
    class Attempt {
        +UUID id
        +UUID user_id
        +str exercise_type
        +str status
        +str? cv_job_id
        +str original_video_ref
        +str? annotated_video_url
        +JSONB? result
        +int? overall_score
        +str? error_code
        +datetime created_at
        +datetime? completed_at
        +datetime expires_at
        +datetime consent_at
    }
    class RefreshToken {
        +UUID id
        +UUID user_id
        +str token_hash
        +datetime issued_at
        +datetime expires_at
        +datetime? revoked_at
    }
    User "1" --> "*" Attempt : posee
    User "1" --> "*" RefreshToken : posee
```

*(El sufijo `?` marca un campo nullable en la base de datos.)*

Estos son los 3 únicos modelos ORM reales (`backend/app/models/`). La propuesta original de
`memoria-ada-outline.md` §5 imaginaba clases separadas `Exercise`, `Score`, `Feedback/Tip` y
`VideoAsset` — ninguna existe como tabla o clase independiente en el sistema real. El score por
repetición, los códigos de error (`knee_valgus`/`insufficient_depth`/`excessive_forward_lean`) y
los consejos de mejora viven como **JSON anidado dentro de `Attempt.result`**, con la forma que
define el contrato de respuesta de cv-service — no como filas o clases propias. `exercise_type` es
un campo de texto plano, no una entidad `Exercise` normalizada, ya que hoy solo existe un ejercicio
soportado (sentadilla). Esta es una simplificación deliberada del sistema real, no una omisión de
este diagrama.
