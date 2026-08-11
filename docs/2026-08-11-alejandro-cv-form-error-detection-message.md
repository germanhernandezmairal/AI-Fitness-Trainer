# Mensaje a Alejandro: detección de errores de forma en cv-service

**Fecha:** 2026-08-11
**Autor:** Compilado con Claude, a partir de
`docs/superpowers/specs/2026-08-07-cv-form-error-detection-request-design.md` (aprobado)
**Estado:** BORRADOR — pendiente de que Germán lo envíe a Alejandro directamente (no enviado por Claude)
**Relacionado:** `docs/superpowers/specs/2026-08-07-cv-form-error-detection-request-design.md`

---

**Asunto: Detección de errores de forma en cv-service (`rep.errors`)**

Hola Alejandro,

Te escribo por un gap que encontramos entre el frontend y `cv-service`. El frontend ya renderiza `rep.errors` por cada repetición (`knee_valgus`, `insufficient_depth`, `excessive_forward_lean`) con su propia tabla de mensajes, pero en `pipeline.py` cada rep se sigue construyendo con `"errors": []` fijo (`build_rep`, línea 74). El contrato original solo nombraba esos tres códigos como catálogo cerrado, sin definir nunca la lógica de detección ni los umbrales — así que esto no quedó pendiente por descuido, simplemente nunca se diseñó.

Para dos de los tres tengo una propuesta concreta de punto de partida (ajustable contra tus propios videos de referencia); para los otros dos prefiero plantearte la pregunta abierta en vez de asumir algo desde tu API.

**1. `insufficient_depth`** — reutiliza la constante `GOOD_DEPTH_MIN` que ya existe:

```python
if rep["min_knee_angle_deg"] > GOOD_DEPTH_MIN:
    rep["errors"].append("insufficient_depth")
```

Una rep cuyo ángulo mínimo nunca bajó de 70° no llegó a la profundidad buena. No pide landmarks nuevos, es un `if` dentro de `build_rep` o justo después de calcular `min_angle_in_rep`.

**2. `excessive_forward_lean`** — esta sí requiere una señal nueva: el landmark de hombro (`RIGHT_SHOULDER`), que MediaPipe ya expone pero el pipeline no usa todavía. La idea es medir la inclinación del torso respecto a la vertical (vector cadera→hombro contra el eje vertical de la imagen) en el frame donde ocurre el ángulo mínimo de rodilla de la rep:

```python
def torso_lean_from_vertical(hip, shoulder) -> float:
    """Ángulo entre el vector cadera->hombro y la vertical, en grados.
    0° = torso perfectamente vertical."""
    vertical = np.array([0, -1])  # "arriba" en coordenadas de imagen (y decrece hacia arriba)
    v = np.array(shoulder) - np.array(hip)
    cosine = np.dot(v, vertical) / (np.linalg.norm(v) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
```

Umbral de partida sugerido: `lean > 45°` → `excessive_forward_lean`. Para esto `segment_reps` necesitaría recordar en qué *frame* ocurrió el ángulo mínimo (hoy solo guarda el valor), para poder recuperar hombro/cadera en ese instante exacto — cómo reestructurar eso internamente lo dejo totalmente a tu criterio.

**3. `knee_valgus`** — acá no tengo propuesta concreta, a propósito. `pipeline.py` asume una sola cámara lateral (solo usa landmarks del lado derecho), y `knee_valgus` es un defecto del plano frontal — se ve de frente, no de lado. Dos ideas sobre la mesa, sin que ninguna sea la que prefiero:
- MediaPipe da una estimación de profundidad (eje Z) incluso con una sola cámara, aunque es conocida por ser ruidosa — podría compararse la posición de la rodilla respecto a la línea cadera-tobillo, pero con confianza baja.
- O no intentarlo esta ronda y dejarlo como limitación conocida, hasta decidir (más a nivel de producto que de código) si vale la pena pedirle al usuario que grabe también de frente.

Preferimos pedirte los tres códigos igual en esta ronda, marcando este como de confianza baja si lo implementás, en vez de excluirlo — mejor una señal imperfecta que ninguna, y es el único de los tres sin ninguna cobertura hoy.

**4. Curva de scoring por profundidad** — esto es aparte, una anomalía que vimos en la verificación end-to-end: un squat real, limpio y profundo (~39-44° de ángulo de rodilla) puntuó 7-22/100, porque `score_from_angle` penaliza simétricamente cualquier ángulo fuera de `[GOOD_DEPTH_MIN, GOOD_DEPTH_MAX]` = `[70, 100]` — tanto quedarse corto como pasarse de profundidad. Con `insufficient_depth` a punto de existir como código de error explícito, tal vez el score general ya no debería penalizar pasarse de profundo, solo quedarse corto — pero también hay argumento de riesgo de lesión en profundidades extremas, así que es una decisión de filosofía de entrenamiento tanto como de código. Te la dejo a vos, no te propongo un umbral o curva de reemplazo.

Para testing, mismo patrón que ya usa `test_pipeline.py`: las funciones nuevas (`torso_lean_from_vertical`, la condición de `insufficient_depth`, lo que definas para `knee_valgus`) se prueban con datos sintéticos, sin depender de MediaPipe ni video real.

Cualquier duda, hablamos. ¡Gracias!
