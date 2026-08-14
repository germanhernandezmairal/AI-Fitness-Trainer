# 3. Planificación

> Fuente: `docs/superpowers/specs/2026-08-14-memoria-cap3-planificacion-design.md` (diseño
> aprobado). Fechas y fases derivadas directamente del historial de `git log` sobre `main` y
> `origin/cv-pipeline`, no estimadas.

Este proyecto se ha desarrollado en dos pistas paralelas que convergen en el contrato de API
backend↔servicio de visión artificial: la pista **Fullstack** (aplicación web, backend, base de
datos, infraestructura) y la pista **Datos/IA**, a cargo de Alejandro (pipeline de detección de
pose, cálculo de ángulos articulares, scoring). El diagrama y la narrativa que siguen cubren el
periodo real transcurrido hasta la fecha de redacción de este capítulo (14 de agosto de 2026); no
proyectan fases futuras aún sin fechas confirmadas (despliegue en AWS, capítulos restantes de la
memoria, mejoras de precisión del pipeline de visión).

```mermaid
gantt
    title Planificación real del proyecto (23 jul – 14 ago 2026)
    dateFormat YYYY-MM-DD
    section Fullstack
    Concepción y planificación          :done, p1, 2026-07-23, 2026-07-27
    API de intentos (backend)           :done, p2, 2026-07-28, 2026-08-03
    Autenticación real                  :done, p4, 2026-08-04, 1d
    Frontend v1                         :done, p5, 2026-08-04, 2026-08-07
    Consolidación de contrato y cap. 4  :done, p6, 2026-08-07, 2026-08-11
    Pulido de diseño del frontend       :done, p7, 2026-08-12, 1d
    Seguimiento del pulido de frontend  :done, p8, 2026-08-13, 2026-08-14
    section Datos/IA (Alejandro)
    MVP del pipeline de visión          :done, p3, 2026-07-27, 2026-08-04
```
