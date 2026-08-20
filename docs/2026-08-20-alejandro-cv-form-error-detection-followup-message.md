# Mensaje a Alejandro: seguimiento sobre detección de errores de forma

**Fecha:** 2026-08-20
**Autor:** Compilado con Claude, a partir de una revisión de código (`code-review high`) sobre
`origin/cv-form-error-detection` (commits `aefbc6f`/`737db16`/`4564dee`)
**Estado:** BORRADOR — pendiente de que Germán lo envíe a Alejandro directamente (no enviado por Claude)
**Relacionado:** `docs/2026-08-11-alejandro-cv-form-error-detection-message.md` (el pedido original),
`docs/superpowers/specs/2026-08-07-cv-form-error-detection-request-design.md`

**Estado del merge:** la rama ya se integró en `main` (fast-forward, sin cambios) — esto no bloquea
nada, son hallazgos para una vuelta futura.

---

**Asunto: Revisión de `insufficient_depth`/`excessive_forward_lean` — un bug real en la fórmula de inclinación**

Hola Alejandro,

¡Gracias por la implementación! Ya la integramos a `main`. Cubriste todo lo que pedimos:
`insufficient_depth` con la constante que ya existía, `excessive_forward_lean` con el landmark de
hombro, `knee_valgus` documentado como limitación conocida (justo la decisión que dejamos abierta),
y de paso arreglaste la anomalía de la curva de scoring con fuentes citadas — buen trabajo, sobre
todo lo de `GOOD_DEPTH_ANGLE_DEG` con Schoenfeld/NSCA.

Pasamos el diff por una revisión de código antes de avisarte, y encontramos un bug real en
`torso_lean_from_vertical` — y vale aclarar: **es el mismo bug que ya tenía la fórmula que te
propusimos** en el mensaje original, no algo que vos introdujiste. Se nos había pasado a nosotros
también.

**1. La fórmula no distingue dirección — solo mide inclinación, no *hacia dónde*.**

```python
def torso_lean_from_vertical(hip, shoulder) -> float:
    vertical = np.array([0, -1])
    v = np.array(shoulder) - np.array(hip)
    cosine = np.dot(v, vertical) / (np.linalg.norm(v) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
```

`cosine` depende solo de la componente vertical de `v` (cadera→hombro), nunca de la componente
horizontal ni de su signo. Resultado: un torso inclinado hacia **atrás** 45°+ da exactamente el
mismo ángulo que uno inclinado hacia **adelante** 45°, y `build_rep` lo etiqueta igual como
`"excessive_forward_lean"` en los dos casos — el feedback que ve el usuario puede estar mal
etiquetado incluso cuando la detección de "hay inclinación" es correcta.

Arreglo sugerido: usar también la componente horizontal con signo (por ejemplo, con
`np.arctan2` sobre ambas componentes, o comprobando el signo de `shoulder[0] - hip[0]` relativo a
la dirección de cámara) para distinguir adelante de atrás, no solo la magnitud.

**2. Relacionado: el `1e-6` en el denominador solo evita la división por cero exacta, no
landmarks casi coincidentes.** Si hombro y cadera caen muy cerca en píxeles (persona lejos de
cámara, glitch de tracking puntual en el frame exacto del ángulo mínimo), el vector resultante es
básicamente ruido de sub-píxel y puede dar un ángulo alto por azar, disparando
`excessive_forward_lean` sin que haya una inclinación real. Valdría la pena un guard de norma
mínima antes de confiar en el ángulo (además del fix de dirección del punto 1).

**3. No es un bug, pero para que lo tengas presente:** como `excessive_forward_lean` solo se
evalúa en el frame del ángulo mínimo de rodilla (no en toda la rep), una inclinación real durante
el descenso que se corrige justo en el fondo no se detecta. Ya lo dejaste documentado en el
código/GLOSARIO como decisión consciente, así que no es una sorpresa — solo lo anoto como fuente
conocida de falsos negativos, por si alguna vez se compara contra video de referencia.

**4. Cosmético:** `torso_lean_from_vertical` reimplementa a mano el mismo cálculo de
`calculate_angle` (dot/norma/arccos/clip) en vez de reusarla con un punto vertical sintético —
por ejemplo `calculate_angle(shoulder, hip, [hip[0], hip[1] - 1])`. Solo para evitar que un
futuro fix (como el guard de norma del punto 2) se aplique a una copia y no a la otra.

**5. Nota de documentación:** `memoria/04-requisitos.md` (RNF-4) todavía cita el nombre viejo de
la constante, `GOOD_DEPTH_MIN`, que este mismo diff renombró a `GOOD_DEPTH_ANGLE_DEG` en
`pipeline.py`. Lo podemos corregir nosotros del lado de la memoria si preferís no tocar eso — avisá.

Nada de esto bloquea lo que ya integramos; son ajustes para una vuelta futura, sobre todo el punto
1 antes de confiar en `excessive_forward_lean` para dar feedback real a usuarios.

¡Gracias de nuevo!
