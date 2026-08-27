# Selector de ejercicio (frontend, solo sentadilla) — Diseño

**Fecha:** 2026-08-27
**Tipo:** cambio acotado (*bounded*) — solo frontend, sin tocar backend, contrato ni cv-service.
**Clasificación:** *bounded*. No modifica ninguna interfaz de la que dependan otros servicios.

## Contexto: cómo fluye `exercise_type` hoy

El tipo de ejercicio **ya está cableado de extremo a extremo** en el MVP, pero el valor se fija
a `"squat"` en el frontend y nunca cambia:

| Paso | Qué pasa | Fichero |
|---|---|---|
| 1. Subida (navegador) | `formData.append("exercise_type", "squat")` — **literal fijo**, sin selector | `frontend/src/components/video-upload-form.tsx:52` |
| 2. `POST /v1/attempts` | `exercise_type: str = Form(...)` — ya es un campo obligatorio | `backend/app/api/attempts.py:38` |
| 3. Validación | `ExerciseType(exercise_type)` contra el enum (`contract.py:24`, solo `SQUAT`), rechaza desconocidos con `unknown_exercise_type` | `backend/app/services/validation.py:87` |
| 4. Persistencia | columna `exercise_type` NOT NULL, escrita al crear el intento, **antes** de enviar el video a CV | `backend/app/models/attempt.py:22` |
| 5. Backend → cv-service | se reenvía como campo de formulario en `POST /v1/jobs` | `backend/app/services/cv_client.py:44` |
| 6. cv-service lo recibe | `main.py` ya parsea y valida `exercise_type` (`_validate_exercise_type`, `SUPPORTED_EXERCISE_TYPES = {"squat"}`) | `cv-service/main.py:73,87` |
| 7. cv-service lo ignora en el análisis | `main.py` no lo pasa a `run_job` → `analizar_video`; `pipeline.py:265` fija `"squat"` en el resultado | `cv-service/pipeline.py` |

Es decir: la fontanería para transportar un tipo de ejercicio ya existe. Lo único que falta a
nivel de producto es que el frontend deje de mandar un literal.

## Objetivo

Que el formulario de subida ofrezca un **selector real** de ejercicio. Solo "Sentadilla" es
seleccionable (es lo único que `cv-service` soporta); el resto se muestra deshabilitado con
"(próximamente)" para comunicar el *roadmap* sin permitir enviar un valor que el backend o
cv-service rechazarían.

## Diseño

**Ficheros tocados:** `frontend/src/components/video-upload-form.tsx` y su test
(`frontend/tests/unit/components/video-upload-form.test.tsx`). Nada más.

1. **Constante a nivel de módulo** (junto a `ALLOWED_EXTENSIONS`):

   ```ts
   const EXERCISE_OPTIONS = [
     { value: "squat", label: "Squat", available: true },
     { value: "pushup", label: "Push-ups", available: false },
     { value: "pullup", label: "Pull-ups", available: false },
   ] as const;
   ```

2. **`<select>` nativo** (no hay componente `Select` de shadcn en `src/components/ui/`; un
   `<select>` nativo con estilos Tailwind evita añadir dependencia), con un `<Label>` "Exercise",
   encima del input de fichero. Las opciones con `available: false` se renderizan `disabled` y
   con el sufijo " (coming soon)".

3. **Estado local:** `const [exerciseType, setExerciseType] = useState("squat")`.

4. **En el submit:** `formData.append("exercise_type", exerciseType)` sustituye al literal
   `"squat"`.

Como solo "squat" es seleccionable, el valor enviado siempre será `"squat"` en la práctica —
pero el camino de código es real.

## Fuera de alcance (explícito)

- Ampliar el enum `ExerciseType` (`backend/app/schemas/contract.py`).
- Cualquier cambio en el backend, el contrato o `cv-service`.
- Etiquetas "bonitas" del tipo de ejercicio en el historial o el resultado
  (`attempt-history-list.tsx` ya hace `capitalize` — se deja como está).
- Coordinación con Alejandro. Este cambio no le afecta.

## El camino "más adelante"

Añadir un ejercicio de verdad (p. ej. flexiones) será, en orden:

1. **cv-service (Alejandro):** `main.py` añade el tipo a `SUPPORTED_EXERCISE_TYPES`, lo pasa a
   `run_job` → `analizar_video`, y `pipeline.py` ramifica por ejercicio en vez de asumir
   sentadilla.
2. **backend:** añadir el valor a `ExerciseType` en `contract.py`.
3. **frontend:** poner `available: true` en `EXERCISE_OPTIONS` para esa opción.

Este diseño deja el paso 3 como una sola línea.

## Pruebas (TDD)

Ampliar `video-upload-form.test.tsx`:

- Renderiza un `<select>` "Exercise" con "Squat" seleccionado por defecto.
- Las opciones "coming soon" se renderizan `disabled`.
- Una subida correcta sigue enviando `exercise_type=squat` en el `FormData`.

`npm test -- --run` en verde; `npm run lint` limpio.
