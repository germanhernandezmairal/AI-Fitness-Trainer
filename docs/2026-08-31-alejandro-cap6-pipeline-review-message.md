# Mensaje a Alejandro: revisión del §6.1 de la memoria (pipeline de CV)

**Fecha:** 2026-08-31
**Autor:** Compilado con Claude, a partir de `cv-service/pipeline.py` y `cv-service/GLOSARIO.md`
**Estado:** BORRADOR — pendiente de que Germán lo envíe a Alejandro directamente (no enviado por Claude)
**Relacionado:** `memoria/06-implementacion.md` §6.1;
`docs/superpowers/specs/2026-08-28-memoria-cap6-implementacion-design.md`;
`docs/2026-08-11-alejandro-cv-form-error-detection-message.md` y
`docs/2026-08-20-alejandro-cv-form-error-detection-followup-message.md` (contactos previos)

**No bloquea nada:** el capítulo está pendiente de integrarse en `main` (se integra esta semana).
Esto es una revisión de exactitud técnica; cualquier corrección entra como commit de seguimiento.

---

**Asunto: Revisión del §6.1 de la memoria — descripción del pipeline de `cv-service`**

Hola Alejandro,

Escribí el §6.1 de la memoria (*Implementación → Pipeline de análisis de movimiento*) a partir de
`cv-service/pipeline.py` y `cv-service/GLOSARIO.md`. Como es tu parte, te paso lo que afirma el
texto para que confirmes o corrijas. Te resumo los puntos sustantivos:

1. **Extracción de pose.** MediaPipe Pose (`mp.solutions.pose`, `mediapipe==0.10.14`), detector
   pre-entrenado usado tal cual, sin entrenar modelo propio. Una única instancia `Pose` por
   trabajo, con `min_detection_confidence=0.5` y `min_tracking_confidence=0.5`. Se leen los
   fotogramas con OpenCV en BGR, se convierten a RGB y se pasan a `pose.process`. De todos los
   landmarks solo se usan **cuatro, todos del lado derecho**: `RIGHT_HIP`, `RIGHT_KNEE`,
   `RIGHT_ANKLE`, `RIGHT_SHOULDER`, desnormalizados a píxeles multiplicando por ancho/alto del
   fotograma. Eso codifica la suposición explícita de **una sola cámara lateral (plano sagital)**
   con el lado derecho hacia la cámara, y es lo que hace que `knee_valgus` sea indetectable por
   diseño. Si ningún fotograma produce pose, el trabajo falla con `no_pose_detected`
   (`NoPoseDetectedError`).

2. **Convención del ángulo de rodilla.** Ángulo interior con vértice en la rodilla de los puntos
   cadera-rodilla-tobillo (`calculate_angle`, en 2D de imagen, con `clip` a [-1, 1] antes de
   `arccos`). Vale ~180° con la pierna extendida y **disminuye** con la flexión. En el texto lo
   describo como aproximadamente el **suplementario** del "ángulo de flexión" de la literatura de
   biomecánica (ángulo interior ≈ 180° − flexión), de modo que ~90° de flexión ≈ 90–100° de ángulo
   interior. **(Ver la nota al final sobre la palabra "complementario" en el comentario del
   código.)** Digo también que `torso_lean_from_vertical` es solo la **magnitud** de la inclinación
   del torso (no distingue adelante de atrás) y que esa distinción la resuelve
   `is_excessive_forward_lean`.

3. **Segmentación en repeticiones.** Máquina de estados de **dos estados** (*de pie* /
   *en repetición*) en `segment_reps`, con `STANDING_THRESHOLD = 160°` como frontera. Al abrir la
   rep se guarda el fotograma inicial y los cuatro landmarks; mientras dura, se guarda el **ángulo
   mínimo** y los landmarks *de ese fotograma concreto* (para poder evaluar la inclinación en el
   punto más bajo, no en uno cualquiera). Una rep que empieza y nunca vuelve a "de pie" (video
   cortado a mitad de rep) se **descarta**, no se cuenta. `fps` se lee de OpenCV (`CAP_PROP_FPS`,
   30 por defecto); los tiempos de rep son `nº fotograma / fps` redondeado a dos decimales.

4. **Puntuación por rep.** `score_from_angle` es una curva **de un solo lado**:
   `GOOD_DEPTH_ANGLE_DEG = 100°`, `PENALTY_PER_DEGREE = 3`; por debajo o igual al umbral no se
   penaliza (bajar más nunca resta), por encima se restan 3 puntos/grado con suelo en 0. La global
   (`overall_score`) es la media de las por-rep, redondeada, 0 si no hubo reps. Cito el
   razonamiento tal como está en `GLOSARIO.md`: **Schoenfeld (2010)** (*Squatting Kinematics and
   Kinetics…*) y la posición de la **NSCA** (*Considerations for Squat Depth*) de que la evidencia
   no sostiene que la sentadilla completa exponga la rodilla a fuerzas dañinas. Menciono que antes
   había una banda de dos límites (`GOOD_DEPTH_MIN`/`GOOD_DEPTH_MAX` = 70°–100°) colapsada a este
   único umbral.

5. **`excessive_forward_lean`.** Describo `is_excessive_forward_lean(cadera, rodilla, tobillo,
   hombro)` como que solo marca el error si se cumplen **las tres** condiciones: (1) los vectores
   cadera→hombro y tobillo→rodilla miden al menos `MIN_TORSO_VECTOR_NORM_PX = 1 px` (si no, su
   dirección es ruido de sub-píxel y no se marca nada); (2) el hombro se desplaza respecto a la
   cadera hacia el mismo lado horizontal en el que la rodilla queda por delante del tobillo (así
   "adelante" queda definido independientemente de la orientación de la cámara y una inclinación
   hacia atrás no cuenta); (3) la magnitud de `torso_lean_from_vertical` supera
   `EXCESSIVE_LEAN_DEG = 45°`, umbral que marco como punto de partida heurístico, no de la
   literatura. En la *historia* digo que la primera versión solo comprobaba la magnitud, que la
   revisión de código del 20/08/2026 lo detectó y que el commit **`a5ad6b8`** (integrado en `main`
   el 31/08/2026) lo hizo direccional y añadió la comprobación de norma mínima. ¿Está bien
   reflejado, sobre todo el estado post-`a5ad6b8`? También recojo la **limitación documentada** (no
   bug): una sentadilla muy *hip-dominant* / de barra baja puede inclinar el torso hacia adelante
   sin que la rodilla avance sobre el tobillo, y entonces el error no se marca aunque visualmente
   la inclinación sea excesiva.

6. **Para tu información, sobre el video anotado.** (Este commit es mío, no tuyo; lo incluyo solo
   para que el capítulo cuadre, no necesito que revises nada.) En cada fotograma con pose se dibuja
   el esqueleto (`mp_drawing.draw_landmarks` con `POSE_CONNECTIONS`) y el ángulo de rodilla como
   texto (`cv2.putText`, `"<n> deg"`); **todos** los fotogramas se escriben a la salida, anotados o
   no. El códec es `ANNOTATED_VIDEO_FOURCC = "avc1"` (H.264). Explico el porqué de que **no sea el
   `mp4v` obvio**: el `<video>` de los navegadores no decodifica MPEG-4 Part 2, así que un `mp4v`
   se ve como un fotograma en blanco; `avc1` produce H.264 real con este build de OpenCV sin
   post-proceso con `ffmpeg`. Lo describo como un bug real detectado la primera vez que se
   reprodujo en navegador un video del pipeline **real** (commit `eeae94a`).

7. **Naturaleza del pipeline.** Digo que MediaPipe es lo único aprendido y que todo aguas abajo
   (ángulos, máquina de estados, umbrales, puntuación) son **reglas deterministas**, sin conjunto
   de entrenamiento ni cifras de accuracy/precision/recall; que `algorithm_version` es la cadena
   literal `"squat-rules-v1"` y `exercise_type` es `"squat"`.

---

**Una corrección concreta que quería plantearte (nit de redacción, no de lógica):**

El comentario de `cv-service/pipeline.py` (~línea 24, sobre `GOOD_DEPTH_ANGLE_DEG`) dice que el
ángulo interior cadera-rodilla-tobillo es *"el complementario"* del ángulo de flexión de la
literatura. En rigor, como los dos suman **180°** (ángulo interior ≈ 180° − flexión), es el
**suplementario**, no el complementario (el complementario sumaría 90°). El ejemplo numérico del
propio comentario ("~90° de flexión ≈ 90–100° de ángulo interior") es coherente con el
suplementario, así que es solo la palabra. En la memoria (§6.1.2) ya uso "suplementario". Te lo
dejo por si querés ajustar el wording del comentario de tu lado; si preferís, lo mencionamos y
listo, no hace falta que toques nada. (El `GLOSARIO.md` no llega a nombrar la convención con esa
palabra, así que ahí no hay nada que cambiar.)

Si algo de lo anterior está mal o impreciso, decime y lo ajusto en la memoria. ¡Gracias!
