<!--
Fuente: docs/superpowers/specs/2026-09-01-memoria-cap7-evaluacion-design.md (diseño aprobado).
Capítulo retrospectivo: documenta la evaluación realmente hecha (suites automatizadas, dos pruebas
extremo a extremo, pruebas manuales del pipeline sobre vídeo real, y el benchmark del 15/08/2026),
trazada a los requisitos del capítulo 4. Recuentos de pruebas verificados ejecutando las suites el
01/09/2026. Números de latencia/concurrencia citados de §4 (RNF-2/RNF-3), no recalculados aquí.
-->

# 7. Evaluación

## 7.1 Estrategia de evaluación

El sistema tiene **dos objetos de evaluación de naturaleza distinta**.

El **primero es la aplicación web**. Su comportamiento está definido por los requisitos del
capítulo 4 (CU-1…CU-7 y RNF-1…RNF-7), así que se evalúa **verificándola contra esos requisitos**:
pruebas automatizadas por componente, dos pruebas extremo a extremo y comprobaciones manuales a
través de la interfaz en ejecución.

El **segundo es el pipeline de análisis de movimiento** (§6.1). Es un sistema de **reglas
deterministas** sobre un detector de pose pre-entrenado, no un clasificador entrenado: no hay
conjunto de entrenamiento, no hay conjunto de vídeos etiquetados y no aplica una cifra de
*accuracy* / *precision* / *recall* (§6.1.6, §4 RNF-4). Se evalúa **observando su comportamiento
sobre vídeo de sentadilla real** y registrando dónde acierta y dónde falla (§7.5).

**Metodología.** Cada funcionalidad y cada capítulo de esta memoria se construyó siguiendo un flujo
de trabajo dirigido por pruebas (*test-first*); el capítulo 3 lo narra por fases y el historial de
Git muestra los *commits* de pruebas acompañando o precediendo a los de implementación. Las suites
automatizadas son el producto duradero de ese proceso, no un añadido posterior.

**Lo que deliberadamente no se hizo, y por qué es defendible en este TFG:**

- **No se construyó un conjunto de vídeos etiquetados** para validar el pipeline de visión.
  Construir y etiquetar ese conjunto es un proyecto en sí mismo, fuera del alcance de un TFG de dos
  personas con un MVP congelado. La consecuencia —que el objetivo de fiabilidad de RNF-4 queda sin
  cuantificar— se asume abiertamente en §7.6.
- **No hubo una campaña de pruebas formal** más allá de las suites que se entregaron con cada
  funcionalidad: el MVP está congelado, no hay código nuevo contra el que hacer campaña.
- **La evaluación del pipeline (§7.5) es exploratoria**, no sistemática: unos pocos vídeos, sin
  etiquetas de verdad-terreno.
