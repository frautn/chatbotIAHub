# Plan de Investigación-Acción: efectos del tutor LLM socrático monitoreado en Mecánica con Python

**Nota metodológica previa:** como investigación-acción (IA), el objetivo no es demostrar causalidad sino **mejorar cíclicamente la práctica docente** documentando qué ocurre. El contexto confirma que el prototipo está "finalizando el diseño y comenzando la experimentación" [1] y que "todavía no se presentan resultados sistemáticos sobre aprendizaje, consistencia de las calificaciones o impacto en los exámenes" [2]: exactamente el punto de partida de una IA. Los criterios de IA y las técnicas de medición específicas no figuran en el contexto; los aporto desde el conocimiento del campo (Lewin; Kemmis & McTaggart; Stenhouse), y conviene verificarlos antes de citarlos.

---

## 1. Pregunta y objetivos

**Pregunta central:** ¿Cómo transforma la incorporación del tutor socrático monitoreado la práctica docente de la corrección y la retroalimentación, y con qué efectos observables sobre el aprendizaje, la transferencia y la autonomía de los estudiantes en un curso de Mecánica con Python?

**Objetivos:**
- O1: Mejorar la frecuencia, calidad y oportunidad de la retroalimentación formativa (necesidad original del prototipo: que los estudiantes practiquen autónomamente la escritura de resoluciones en sucesivas iteraciones [1]).
- O2: Documentar los efectos del uso del tutor sobre comprensión conceptual, calidad argumentativa escrita y transferencia entre planteo analítico y computacional.
- O3: Detectar y caracterizar la delegación cognitiva (dependencia del tutor) usando la trazabilidad de los diálogos.
- O4: Desarrollar un protocolo de monitoreo e intervención docente sobre las conversaciones, que hoy está identificado como pendiente: el repositorio implementa la infraestructura pero "no determina por sí mismo las reglas institucionales de privacidad, las alertas ni el protocolo de intervención" [2].

## 2. Estructura en ciclos de IA

Cada ciclo sigue la espiral clásica: **planificar → actuar → observar → reflexionar → rediseñar**.

**Ciclo 0 — Línea de base y validación (1 cuatrimestre):**
- Relevamiento inicial: resoluciones manuscritas y códigos de una cohorte sin tutor; encuesta de prácticas de estudio.
- Validación del instrumento: acuerdo entre calificaciones del chatbot (Insuficiente/Regular/Bien, con rúbrica predefinida no visible para el estudiante [1]) y docentes sobre una muestra doble-codificada (kappa ponderado, análisis de discrepancias).
- Producto del ciclo: rúbrica calibrada y confianza en que el chatbot mide razonablemente antes de usarlo para observar efectos.

**Ciclo 1 — Primera implementación (1 cuatrimestre):**
- Actuar: integrar el tutor en 3–4 actividades de foto–corrección–reintento [1] en unidades seleccionadas (p. ej., movimiento de proyectiles, osciladores).
- Observar: trazas completas de diálogos, resoluciones iteradas, códigos, encuestas de experiencia, registro de intervenciones docentes.
- Reflexionar: reunión del equipo docente para analizar qué tipos de error detecta/pasa por alto el tutor, qué preguntas socráticas funcionan, dónde aparece delegación.
- Rediseñar: ajustar system prompts (que ya son específicos por consigna [1]), rúbricas y protocolo de intervención.

**Ciclo 2 — Implementación mejorada (1 cuatrimestre):**
- Repetir con la versión ajustada, incorporando las lecciones del ciclo 1 y comparando indicadores entre ciclos (la comparación temporal reemplaza aquí al grupo de control, coherente con IA).

## 3. Qué medir (y cómo)

**A. Aprendizaje:**
- Pre/post test conceptual por unidad (ítems de mecánica + ítems de lectura/depuración de código Python), con ganancia normalizada.
- Calidad de resoluciones con rúbrica analítica que separe *comprensión conceptual* y *calidad argumentativa* — el sistema actual distingue implícitamente ambas al sugerir "mejoras de claridad y de razonamiento" [1], pero la escala Insuficiente/Regular/Bien es demasiado gruesa para investigación; codificación por docentes ciegos al número de iteración.

**B. Transferencia:**
- Ítems de transferencia analítica→computacional (dado un planteo resuelto, implementarlo) y computacional→analítica (dado un código, explicar el fenómeno físico y detectar errores), resueltos **sin tutor** al final de cada unidad y en el examen.
- Medida distal: desempeño en parcial/final, donde la comunicación escrita del razonamiento es exigible.

**C. Delegación cognitiva (ventaja comparativa de la trazabilidad):**
- Proporción de turnos donde el estudiante pide la respuesta directa vs. intenta argumentar.
- *Uptake*: si la corrección siguiente aborda lo señalado por el tutor o reintenta al azar.
- Profundidad de iteraciones por actividad y su evolución en el cuatrimestre (¿decrece la necesidad de ayuda?).
- Brecha entre desempeño con tutor y sin tutor en problemas isomorfos.
- Autorreporte: escala breve de intenciones de *cognitive offloading* (Risko & Gilbert, 2016, como marco conceptual).

**D. La práctica docente (el foco de la IA):**
- Tiempo docente dedicado a corrección antes/después; frecuencia y tipo de intervenciones sobre las conversaciones; casos donde el monitoreo reveló errores conceptuales masivos que dispararon ajustes de clase.
- Diario de campo del equipo docente por ciclo.

## 4. Analítica de las trazas

- Esquema de codificación de actos de diálogo (movimientos socráticos del tutor, autoexplicaciones, pedidos de respuesta, errores conceptuales) aplicado a una muestra por ciclo.
- Métricas automáticas sobre la totalidad de los registros (OpenWebUI los conserva al estar integrado vía LTI a Moodle [1]): n° de iteraciones, longitud de mensajes, tiempo entre turnos, temas consultados.
- Para el componente computacional: versionado de códigos, errores de ejecución sucesivos, relación entre lo discutido con el tutor y lo modificado en el script.

## 5. Ética y gobernanza

- Consentimiento informado; anonimización de fotos de manuscritos (datos personales); definir quién accede a los diálogos.
- El protocolo de monitoreo/intervención debe construirse como **entregable explícito del proyecto**, dado que está señalado como no resuelto [2]: umbrales de alerta, cuándo y cómo interviene el docente, reglas de privacidad institucional.
- Declarar en la propuesta que la calificación del chatbot es formativa (es "la forma que tiene el estudiante de medir su avance" [1]), no sumativa.

## 6. Productos para la convocatoria

1. Informe de línea de base y validación del corrector (Ciclo 0).
2. Protocolo de monitoreo e intervención docente (transferible a otros cursos; las notas de diseño ya prevén que "podría servir para otros usos docentes" [2]).
3. Informe por ciclo con indicadores de aprendizaje, transferencia y delegación.
4. Rúbricas, consignas y system prompts documentados y reutilizables.
5. Artículo de experiencia: la línea de "propuesta pedagógica de práctica y acompañamiento" es presentable por separado de la infraestructura de monitoreo [2], lo que da dos productos publicables.

## 7. Cronograma sugerido (4 cuatrimestres)

| Cuat. | Hito |
|---|---|
| 1 | Ciclo 0: línea de base, validación del corrector, protocolo ético |
| 2 | Ciclo 1: implementación inicial + observación |
| 3 | Reflexión, rediseño; Ciclo 2 |
| 4 | Análisis integrado, protocolo de intervención consolidado, escritura |

---

**Nota sobre el encuadre:** la medición de "efectos" en IA es descriptiva-comparativa entre ciclos y entre desempeño con/sin tutor, sin inferencia causal estricta. Si la convocatoria exige evidencia causal, habría que reformular como estudio cuasi-experimental; si acepta IA, este plan es coherente y el componente más novedoso para evaluadores es probablemente el O3+O4 (delegación medida con trazas y protocolo de intervención).
