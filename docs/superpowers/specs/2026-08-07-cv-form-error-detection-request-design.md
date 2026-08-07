# Design: Solicitud de detección de errores de forma para cv-service

**Fecha:** 2026-08-07
**Autor:** Compilado con Claude, a partir de una revisión de `cv-service/pipeline.py` en `main`
**Estado:** APROBADO (2026-08-07) — pendiente de convertirse en mensaje para Alejandro
**Relacionado:** `docs/2026-07-27-cv-gym-exercise-design.md` §7 (catálogo cerrado de códigos de
error), `docs/superpowers/specs/2026-08-04-cv-service-mvp-design.md` §6 (dejó esto explícitamente
fuera de alcance del MVP), `cv-service/pipeline.py` (implementación actual).

---

## 0. Contexto y objetivo

El frontend (`worktree-frontend-v1`, PR abierta) ya renderiza `rep.errors` por repetición —
`knee_valgus`, `insufficient_depth`, `excessive_forward_lean` — con una tabla de copy propia. Pero
`cv-service/pipeline.py` todavía no detecta ninguno de los tres: cada rep se construye con
`"errors": []` fijo (`build_rep`, línea 74). El contrato original (`docs/2026-07-27-cv-gym-exercise-
design.md`) solo nombra los tres códigos como "catálogo cerrado", sin definir la lógica de
detección ni umbrales — eso nunca se diseñó.

Además, se detectó una anomalía de scoring en la verificación end-to-end del 2026-08-04: un squat
real, limpio y profundo (~39-44° de ángulo de rodilla) puntuó 7-22/100, porque `score_from_angle`
penaliza simétricamente cualquier ángulo fuera de `[GOOD_DEPTH_MIN, GOOD_DEPTH_MAX]` = `[70, 100]`
— tanto quedarse corto como pasarse de profundidad. Un squat más profundo que 90° suele
considerarse buena forma, no un defecto.

Este documento no es una implementación — es la base de un mensaje para Alejandro, quien sigue
siendo el dueño de `cv-service/`. No se toca su código en este trabajo.

**Restricción de cámara importante:** `pipeline.py` asume una sola cámara lateral (usa solo
landmarks del lado derecho: `RIGHT_HIP`, `RIGHT_KNEE`, `RIGHT_ANKLE`). `insufficient_depth` y
`excessive_forward_lean` son observables en el plano sagital (de lado) y encajan bien con esa
cámara. `knee_valgus` (rodillas cayendo hacia adentro) es, en cambio, un defecto del plano frontal
— se ve mejor de frente, no de lado. Esto condiciona todo el diseño de abajo.

## 1. `insufficient_depth` — propuesta concreta

Reutiliza la constante `GOOD_DEPTH_MIN` que ya existe en el código:

```python
if rep["min_knee_angle_deg"] > GOOD_DEPTH_MIN:
    rep["errors"].append("insufficient_depth")
```

Una rep cuyo ángulo mínimo nunca bajó de 70° no llegó a la profundidad buena. No requiere
landmarks nuevos ni cambios estructurales — un `if` dentro de `build_rep` o inmediatamente después
de calcular `min_angle_in_rep`. Punto de partida sugerido; a confirmar/ajustar contra su propio set
de videos de referencia.

## 2. `excessive_forward_lean` — propuesta concreta, una señal nueva

Requiere el landmark de hombro (`RIGHT_SHOULDER`), que MediaPipe ya expone pero que `pipeline.py`
no usa todavía. Propuesta: medir la inclinación del torso respecto a la vertical (vector
cadera→hombro contra el eje vertical de la imagen) en el frame donde ocurre el ángulo mínimo de
rodilla de la rep (el punto más bajo del squat):

```python
def torso_lean_from_vertical(hip, shoulder) -> float:
    """Ángulo entre el vector cadera->hombro y la vertical, en grados.
    0° = torso perfectamente vertical."""
    vertical = np.array([0, -1])  # "arriba" en coordenadas de imagen (y decrece hacia arriba)
    v = np.array(shoulder) - np.array(hip)
    cosine = np.dot(v, vertical) / (np.linalg.norm(v) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
```

Umbral de partida sugerido: `lean > 45°` → `excessive_forward_lean`. Requiere que la detección de
reps (`segment_reps`) recuerde en qué frame ocurrió el ángulo mínimo (hoy solo guarda el valor del
ángulo, no el frame) para poder recuperar la posición del hombro/cadera en ese instante exacto —
el resto de la reestructuración interna queda a su criterio. Umbral también a confirmar/ajustar
contra videos reales.

## 3. `knee_valgus` — abierto, esfuerzo best-effort

No hay una propuesta concreta aquí a propósito, por la restricción de cámara del §0. Ideas a poner
sobre la mesa en el mensaje, sin prescribir:

- MediaPipe da una estimación de profundidad (eje Z) incluso con una sola cámara, pero es
  conocida por ser ruidosa — podría usarse para comparar la posición de la rodilla respecto a la
  línea cadera-tobillo, pero con confianza baja.
- Alternativa: no intentarlo esta ronda y dejarlo como una limitación conocida hasta que se decida
  (a nivel de producto, no de código) si vale la pena pedir a los usuarios que graben de frente.

Se decidió explícitamente (con Germán, 2026-08-07) pedir los tres códigos igual, marcando este
como de confianza baja, en vez de excluirlo de la ronda — es mejor tener una señal imperfecta que
ninguna, y es el único de los tres códigos sin cobertura hoy.

## 4. Curva de scoring por profundidad — pregunta abierta, no una propuesta

Plantear la anomalía (squat profundo y limpio puntuando 7-22/100) y la observación de que, con
`insufficient_depth` a punto de existir como código de error explícito, quizás el score general no
debería penalizar pasarse de profundo — solo quedarse corto. Pero es una decisión de filosofía de
entrenamiento tanto como de código (hay argumento de riesgo de lesión en profundidades extremas), y
se decidió explícitamente (con Germán, 2026-08-07) dejarla en manos de Alejandro en vez de proponer
un umbral o curva de reemplazo.

## 5. Testing esperado

Sin cambios respecto al patrón que ya usa `cv-service/tests/test_pipeline.py`: las funciones puras
nuevas (`torso_lean_from_vertical`, la condición de `insufficient_depth`, lo que resulte para
`knee_valgus`) se prueban con datos sintéticos, igual que `calculate_angle`/`score_from_angle`/
`segment_reps` hoy — no dependen de MediaPipe ni de video real.

## 6. Siguientes pasos

Este documento es la base técnica de un mensaje en español para Alejandro (fuera de este repo,
enviado directamente por Germán — no por Claude). El mensaje debe:
- Explicar el gap (frontend ya renderiza `rep.errors`, siempre vacío hoy).
- Proponer §1 y §2 como punto de partida concreto, marcados explícitamente como ajustables.
- Plantear §3 y §4 como preguntas abiertas para que él decida el enfoque.

No hay tareas de implementación de Claude en este documento — a diferencia de los specs previos de
este proyecto, no continúa hacia `superpowers:writing-plans`.
