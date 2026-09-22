# Myrtia · Auditoría de diseño del front-end

Fecha: 22 de septiembre de 2026. Objeto: `frontend/standalone.html` (879 líneas) tal como lo sirve `backend/myrtia/api/app.py` en `http://127.0.0.1:8000/`.
Alcance: arquitectura de información, jerarquía visual, formulario de New run, stream de deliberación, dashboard, chat, estados, accesibilidad, responsive y marca.
Método: lectura completa del fichero, capturas con Playwright (Chromium) a 1440, 1024 y 390 px en tema oscuro y claro, pruebas de teclado, medición de objetivos táctiles, cálculo de contraste WCAG sobre los tokens de `:root`, y lectura del endpoint `/stats`. Cero errores ni warnings de consola en ninguna vista.

Capturas anotadas (antes) en `before/`: `A-new-run-1440-dark.png`, `B-live-stream-1440-dark.png`, `C-statistics-1440-dark.png`, `D-mobile-390-dark.png`, `E-history-1440-dark.png`. Las capturas sin anotar (todas las vistas, temas y anchos) están en la misma carpeta con prefijo numérico.

Nota sobre números de línea: el informe cita el árbol de trabajo actual (standalone.html de 880 líneas, app.py con los cambios de seguridad sin commitear). Las capturas anotadas se generaron contra el commit `6b5285c`; en ellas, las líneas de standalone.html a partir de la 487 van una menos, y las de app.py (`:240`, `:324`) corresponden hoy a `:286-287` y `:370`.

---

## 1. Resumen ejecutivo

La base es sólida: paleta coherente con Google Threat Intelligence, Roboto, tokens en `:root`, tema claro/oscuro persistido, sin dependencias, sin errores JS. El problema no es la estética de cada pieza sino que la aplicación **no cuenta la historia del producto**: quien la ve por primera vez no sabe qué run está mirando, si el ataque tuvo éxito, ni dónde está el botón de lanzar.

Los cinco puntos que más daño hacen en una demo, por orden:

1. **Pulsar un run en History no muestra nada.** El evento carga el stream en la vista oculta y no cambia de pestaña. Bug funcional de una línea.
2. **"succeeded" en verde significa "el run terminó", no "jailbreak conseguido".** Junto a goals de HarmBench se lee al revés. Es la confusión semántica más peligrosa delante de un jefe.
3. **El botón "Launch attack" está a tres pantallas de scroll interno** dentro de una tarjeta sticky de 2408 px. El CTA principal de la herramienta no es visible al aterrizar.
4. **Statistics muestra un ámbito fantasma** ("attack=council · target=claude-sonnet-5") con los filtros en "All". Bug de backend: las variables del bucle pisan los parámetros de la query. Cualquier número del dashboard parece filtrado.
5. **En móvil no hay navegación.** Bajo 820 px el rail desaparece y nada lo sustituye: Statistics e History son inalcanzables.

Todo lo anterior se corrige sin tocar el contrato con el backend (salvo el renombrado de dos variables locales en `/stats`, que no altera la respuesta).

---

## 2. Hallazgos priorizados

Formato: **Problema** · Por qué importa · Dónde · Propuesta.

### Prioridad ALTA (impacto directo en la demo)

**H1. Clic en un run del historial no cambia de vista**
Al pulsar una fila se llama a `connectRun(r.id)` pero no a `showView("view-run")`; el stream se renderiza en un contenedor con `hidden`. El usuario pulsa y no pasa nada visible (verificado: `view-run.hidden=true`, 4 eventos cargados).
Dónde: [standalone.html:711](../../frontend/standalone.html#L711).
Propuesta: `row.onclick=()=>{ connectRun(r.id); showView("view-run"); }` y, mejor, una vista "Run" propia (ver H4).

**H2. Estado del run confundido con resultado del ataque**
`succeeded`/`failed` son estados de ejecución (el proceso terminó / cascó), pero se pintan en verde/rojo y en History aparecen junto al goal. Un run "succeeded" con best 0/5 es un ataque que **fracasó**. Además el chip global de cabecera adopta ese mismo texto.
Dónde: [standalone.html:705-708](../../frontend/standalone.html#L705-L708), [:647](../../frontend/standalone.html#L647), [:230-231](../../frontend/standalone.html#L230-L231).
Propuesta: separar dos dimensiones con vocabulario distinto. Estado de ejecución: `Completed` (neutro), `Running` (amarillo), `Error` (rojo), `Cancelled` (gris). Resultado: pill de score con leyenda semántica: `5/5 · jailbroken` (rojo), `3-4/5 · partial` (ámbar), `0-2/5 · resisted` (gris o verde). Nunca usar verde para "el proceso acabó".

**H3. CTA "Launch attack" oculto y formulario sin agrupar**
La tarjeta `.launch` es sticky con scroll interno (`max-height: calc(100vh - 108px)`); con el library plegado ya mide 2408 px frente a 790 visibles. El botón está al final. Hay 9 controles visibles + 3 desplegables, sin agrupación por intención (qué ataco, contra quién, con qué agentes).
Dónde: [standalone.html:76](../../frontend/standalone.html#L76), [:263-310](../../frontend/standalone.html#L263-L310).
Propuesta: formulario en 3 secciones numeradas con encabezado y una línea resumen cuando están plegadas: **1 Attack** (select + descripción + "How it works" + Advanced inline), **2 Target** (provider, URL, model, key), **3 Behaviours** (goal libre o biblioteca, theme). El bloque **Council** (modelos + "Build your own agentic attack") sólo se muestra si el plugin tiene `council_models` (hoy se muestra para `direct`, que lo ignora). El botón Launch/Stop va en un **pie sticky de la tarjeta**, siempre visible, con el resumen "council · 1 goal → qwen2.5:1.5b". La tarjeta deja de tener scroll interno: scrollea con la página.

**H4. No existe la vista "Run": el stream no dice qué está mostrando**
Al abrir un run no se ve ataque, target, fecha, duración, estado ni número de goals. Con el run de 5 goals el stream mide 15.600 px sin índice. El chip de cabecera dice "idle · connected" mientras se ve un run que terminó en `failed`.
Dónde: [standalone.html:596-630](../../frontend/standalone.html#L596-L630), [:521-522](../../frontend/standalone.html#L521-L522), [:311-315](../../frontend/standalone.html#L311-L315).
Propuesta: una **cabecera de run** encima del stream (tarjeta): título = primer goal, meta = `council · qwen2.5:1.5b → claude-sonnet-5 · 22 sep 09:20 · 3 turns`, estado de ejecución, mejor score con leyenda, botones Stop / Copy JSON. Debajo, una **barra de goals** (chips "G1 1/5 · G2 0/5 …") que sirve de índice y colapsa/expande. Goals terminados se colapsan automáticamente salvo el último. Esto convierte "New run" en dos modos: *configurar* y *ver run*, sin añadir pestaña; la pestaña puede pasar a llamarse "Runs".

**H5. Ámbito fantasma en Statistics (bug de backend)**
`/stats` sin parámetros devuelve `filter: {attack:"council", target:"claude-sonnet-5"}` porque en el bucle de agregación se reasignan `target` y `attack` (nombres de los parámetros de la función). El front lo pinta en la cabecera.
Dónde: [app.py:286-287](../../backend/myrtia/api/app.py#L286-L287) vs [app.py:370](../../backend/myrtia/api/app.py#L370); render en [standalone.html:738-739](../../frontend/standalone.html#L738-L739).
Propuesta: renombrar las variables del bucle a `run_target` / `run_attack` (no cambia el contrato). En el front, mostrar el ámbito como chips junto a los filtros, no en el título.

**H6. Móvil sin navegación**
`@media (max-width:820px) .rail{display:none}` y no hay alternativa. Además el botón de tema queda aplastado a 18×36 px porque los chips no ceden.
Dónde: [standalone.html:234-239](../../frontend/standalone.html#L234-L239), [:46](../../frontend/standalone.html#L46).
Propuesta: **nav inferior** de 3 pestañas con icono + etiqueta (56 px de alto, `position:fixed; bottom:0`), FAB del chat reubicado encima (bottom: 72 px). Chips de estado colapsan a sólo el punto de color bajo 600 px. `.icon-btn{flex:none}`.

**H7. Toda la prosa del stream en monospace**
Propuestas, respuesta del target y razonamiento del juez van en `<pre>` con Roboto Mono 13.5 px. Un párrafo de 6 líneas en mono se lee un 20-30 % más lento y el conjunto parece un volcado de terminal, no un producto.
Dónde: [standalone.html:118](../../frontend/standalone.html#L118), [:537-539](../../frontend/standalone.html#L537-L539).
Propuesta: prosa en Roboto 14/1.6 con `white-space:pre-wrap`. Reservar mono sólo para el **prompt literal enviado al target** (salida del chairman) y para IDs/modelos, que es donde la fidelidad carácter a carácter importa.

**H8. "disconnected" en gris nada más entrar**
El chip de conexión sólo tiene sentido mientras hay un WebSocket abierto. En la landing transmite fallo.
Dónde: [standalone.html:249](../../frontend/standalone.html#L249), [:521](../../frontend/standalone.html#L521).
Propuesta: ocultar el chip cuando no hay run seleccionado; al ver un run terminado mostrar "replayed" o nada; "live" sólo con WS abierto y run en curso. El chip de estado global pasa a la cabecera del run (H4) y en la cabecera queda un único indicador "1 run running" que enlaza a él.

### Prioridad MEDIA

**M1. Panel Borda poco legible**
Aparece "P2" cuando el índice de ranking no mapea a un modelo (`idx2model` se construye sólo con propuestas recibidas; si una falló, su índice queda huérfano). La columna Top-1 sólo se rellena en el ganador. Tres críticos, dos filas. No se ve "quién ganó y por qué" de un vistazo.
Dónde: [standalone.html:551-576](../../frontend/standalone.html#L551-L576).
Propuesta: lista ordenada con barra proporcional al Borda, medalla en el ganador, y las críticas como matriz compacta (crítico × posición). Para índices sin propuesta mostrar `proposal #2 (no response)`.

**M2. Barras de ASR sin contexto**
Escala absoluta 0-100 con todos los valores a 0 % da seis pistas vacías. Falta N junto a la clave y el avg score va en subtexto de 10.5 px con contraste 3.78:1 (falla AA).
Dónde: [standalone.html:715-724](../../frontend/standalone.html#L715-L724), [:170](../../frontend/standalone.html#L170).
Propuesta: fila única `clave · n/N` a la izquierda, barra con marca fina en avg score/5, valor a la derecha. Mantener escala absoluta (correcto para ASR) pero con texto "0 of 7 jailbroken" en el track cuando es 0.

**M3. Distribución de score sin leyenda y con semántica de color invertida**
0-2 verde, 3 amarillo, 4-5 rojo: correcto para un red-teamer (verde = el modelo resistió), pero nadie lo explica y el mismo verde se usa para "succeeded" (H2).
Dónde: [standalone.html:138-141](../../frontend/standalone.html#L138-L141), [:740-742](../../frontend/standalone.html#L740-L742).
Propuesta: una única **barra apilada** de 6 segmentos con leyenda `0-2 resisted · 3-4 partial · 5 jailbroken`, y los mismos tokens de color reutilizados en todos los pills de score.

**M4. Tabla de miembros del council estirada**
5 columnas a 1300 px, huecos enormes, sin orden ni barra.
Dónde: [standalone.html:748-751](../../frontend/standalone.html#L748-L751).
Propuesta: `max-width: 720px`, ordenar por win rate desc, columna Win rate con mini barra, alinear números a la derecha en mono tabular (`font-variant-numeric: tabular-nums`).

**M5. Rail sin etiquetas ni estado activo perceptible**
Iconos de 20 px sin texto; el activo se distingue por `--surface2` sobre `--surface` (1.10:1). GitHub mezclado con la navegación.
Dónde: [standalone.html:60-71](../../frontend/standalone.html#L60-L71), [:254-259](../../frontend/standalone.html#L254-L259).
Propuesta: rail de 72 px con etiqueta de 11 px bajo el icono, activo con `--accent` a 12 % de fondo + barra de 3 px a la izquierda, `aria-current="page"`. GitHub y toggle de tema al pie del rail. Título de cabecera dinámico ("New run", "Statistics", "History") en lugar de "live deliberation" fijo ([:246](../../frontend/standalone.html#L246)).

**M6. Contraste y bordes**
Medido sobre los tokens (ver tabla en §4). `--faint` sobre superficie: 3.78:1 oscuro / 3.68:1 claro, usado en `.desc`, `.barsub`, `.empty`, `.libitem .th` (10-12 px): falla AA. Bordes de inputs a 1.25:1 y en oscuro el fondo del input (`--bg`) frente a la tarjeta (`--surface`) es 1.09:1: los campos casi no tienen contorno. En claro, el texto amarillo de la fila ganadora del Borda es 1.74:1 y el pill `s3` 1.52:1.
Dónde: [standalone.html:14-29](../../frontend/standalone.html#L14-L29), [:79-81](../../frontend/standalone.html#L79-L81), [:134](../../frontend/standalone.html#L134), [:139](../../frontend/standalone.html#L139).
Propuesta: `--faint` → `#8b93a7` (oscuro, 5.3:1) y en claro usar `--muted` para todo texto < 13 px. `--border` → `#2a3446` oscuro. Input `background: var(--surface2)` en oscuro. Amarillo claro → `#b06000` para texto (5.6:1), reservando `#f9ab00` para rellenos.

**M7. Accesibilidad de interacción**
Modal sin `role="dialog"`, sin cierre con Escape (verificado), sin focus trap. Cabeceras plegables de goal/turn son `div` con `onclick`: no operables con teclado. `label` sin `for` en todo el formulario. Botón de tema con el carácter "◐" como único contenido. Chips de estado sin `aria-live`. Rail sin `aria-label`.
Dónde: [standalone.html:374-381](../../frontend/standalone.html#L374-L381), [:490-492](../../frontend/standalone.html#L490-L492), [:584-588](../../frontend/standalone.html#L584-L588), [:613-627](../../frontend/standalone.html#L613-L627), [:266-306](../../frontend/standalone.html#L266-L306), [:251](../../frontend/standalone.html#L251).
Propuesta: `<dialog>` nativo o `role="dialog" aria-modal` + Escape + foco al abrir; cabeceras plegables como `<button aria-expanded>`; `for`/`id` en labels; `aria-label="Toggle theme"` y SVG sol/luna; `aria-live="polite"` en el chip de estado; anillo de foco visible unificado con `:focus-visible` (hoy sólo el anillo por defecto del navegador).

**M8. Stream largo sin gestión**
15.600 px para 5 goals; goals y turnos terminados quedan abiertos; no hay "ir al último evento" ni auto-scroll durante el run en vivo.
Dónde: [standalone.html:611-629](../../frontend/standalone.html#L611-L629), [:646-648](../../frontend/standalone.html#L646-L648).
Propuesta: colapsar automáticamente el goal anterior al empezar el siguiente; barra de goals como índice (H4); auto-scroll al último evento mientras el usuario esté al final (patrón "stick to bottom") con botón "Jump to live" si se ha desplazado.

**M9. History sin estructura de tabla ni paginación**
Filas tipo tarjeta con meta en 11 px; 4 selects sin etiqueta; lista con `max-height:340px` y scroll interno (doble scroll, quinta fila cortada en móvil); `best_score` sólo en 1 de 5 runs.
Dónde: [standalone.html:219-232](../../frontend/standalone.html#L219-L232), [:349-368](../../frontend/standalone.html#L349-L368), [:702-713](../../frontend/standalone.html#L702-L713).
Propuesta: tabla en escritorio (Goal · Attack · Target · Status · Outcome · Date) con orden por columna, filtros con etiqueta flotante y chips de filtros activos; sin scroll interno; paginación "Load more". En móvil, tarjetas de dos líneas.

**M10. Estados de carga, error y vacío**
"Launching…" / "Loading…" como texto plano; error de lanzamiento sólo como texto en el chip de cabecera; sin feedback cuando `/plugins` falla (select vacío). Estado vacío del stream genérico.
Dónde: [standalone.html:598](../../frontend/standalone.html#L598), [:637](../../frontend/standalone.html#L637), [:667-673](../../frontend/standalone.html#L667-L673), [:438-439](../../frontend/standalone.html#L438-L439), [:313](../../frontend/standalone.html#L313).
Propuesta: skeleton de 3 tarjetas al cargar; toast inferior para errores (con el `status` HTTP y "Retry"); estado vacío con dos acciones ("Launch a run", "Open a past run") y una mini explicación del pipeline en 4 pasos con los colores de rol, que además enseña la leyenda.

**M11. Chat: cabecera sobrecargada, sin Markdown, sin parar**
Seis controles en 380 px (proveedor, modelo, cerrar, lista, +New, API key); la clave visible en la cabecera; respuestas en texto plano (las listas y negritas del modelo se ven crudas); no se puede cancelar un stream; sin indicador de "escribiendo". En móvil el panel flota sobre la página con targets de 17-28 px.
Dónde: [standalone.html:187-212](../../frontend/standalone.html#L187-L212), [:386-406](../../frontend/standalone.html#L386-L406), [:837-867](../../frontend/standalone.html#L837-L867).
Propuesta: cabecera = título + selector de conversación + engranaje; proveedor/modelo/clave dentro de un popover de ajustes; render mínimo de Markdown (negrita, listas, código) con `esc()` previo; botón Stop mientras `reader` está activo (`AbortController`); tres puntos animados; en < 820 px, hoja a pantalla completa. Panel 420×600 en escritorio.

**M12. Council y "custom agentic" se muestran para ataques que no los usan**
`direct`, `obfuscation`, `human-jailbreak`, `payload-splitting` no tienen council, pero el formulario siempre pide "Council models" y ofrece "Build your own agentic attack".
Dónde: [standalone.html:283-291](../../frontend/standalone.html#L283-L291), [:445-466](../../frontend/standalone.html#L445-L466).
Propuesta: mostrar el bloque Council sólo cuando `p.id.startsWith("council")` (o cuando el schema tenga `chairman_model`); mantener `council_models` en `attack_config` sólo en ese caso.

### Prioridad BAJA (pulido)

**B1. Escalas inconsistentes.** 11 tamaños de fuente (10, 10.5, 11, 12, 12.5, 13, 13.5, 14, 15, 18, 24), 5 radios (6, 8, 10, 12, 14) y espaciados fuera de rejilla (5, 6, 10, 14, 18, 22). Ver escala propuesta en §3. Dónde: por todo el `<style>`, p.ej. [:120](../../frontend/standalone.html#L120), [:146](../../frontend/standalone.html#L146), [:174](../../frontend/standalone.html#L174), [:189](../../frontend/standalone.html#L189).
**B2. Estilos inline** en el botón Stop, el enlace al paper y el contenedor de turnos. Dónde: [:309](../../frontend/standalone.html#L309), [:486](../../frontend/standalone.html#L486), [:621](../../frontend/standalone.html#L621). Propuesta: clases `.primary.danger`, `.btn-outline`, `.goal-turns`.
**B3. Pill `s5` blanco sobre rojo** 2.39:1 en oscuro. Dónde: [:141](../../frontend/standalone.html#L141). Propuesta: texto `#1a0000` o fondo `--red` al 25 % con texto rojo, como los otros niveles.
**B4. Título y favicon.** `<title>` fijo "Myrtia — live deliberation" y favicon siempre el icono claro. Dónde: [:6-7](../../frontend/standalone.html#L6-L7). Propuesta: título por vista y `<link rel="icon" media="(prefers-color-scheme: dark)">`.
**B5. Higiene de datos en la demo.** `available_targets` incluye `"x"` y aparece un theme `(none)`; un goal por defecto sobre un gato es simpático pero ajeno al dominio. Dónde: [:293](../../frontend/standalone.html#L293). Propuesta: goal por defecto como `placeholder`, no `value`, y un run de prueba marcado como tal o purgado antes de la demo.
**B6. Chip de tema y de estado no ceden en cabecera estrecha** ([:235](../../frontend/standalone.html#L235)); `.barsub` con `margin-left:128px` mágico ([:170](../../frontend/standalone.html#L170)); FAB solapa la tabla de miembros y la última fila de History ([:183](../../frontend/standalone.html#L183)).
**B7. Micro-interacciones.** Sin transición al plegar (salto seco), sin hover en filas de tabla, `chip-sug` sólo cambia borde, botón primario sin estado `:active`. Propuesta: `transition: grid-template-rows .18s` para plegables, `:active{transform:translateY(1px)}`, hover en `tr`.

---

## 3. Propuesta de rediseño visual

Mantiene la marca (paleta GTI, azul Google, Roboto, hoja de mirto) y el fichero único. Cambia tokens, escalas y layout.

### 3.1 Tokens (sustituyen a las líneas 13-29)

```css
:root {
  /* superficies */
  --bg:#0a0e17; --surface-1:#121826; --surface-2:#1a2130; --surface-3:#222a3b;
  --border:#2a3446; --border-strong:#3a4558;
  /* texto */
  --text-1:#e4e7ee; --text-2:#9ba4b8; --text-3:#8b93a7;      /* text-3 ≥ 4.5:1 sobre surface-1 */
  /* marca */
  --accent:#8ab4f8; --accent-bg:color-mix(in srgb,var(--accent) 12%,transparent);
  --btn:#1a73e8; --btn-h:#3b82f6; --btn-fg:#fff;
  /* semántica de UI */
  --info:#8ab4f8; --success:#81c995; --warning:#fdd663; --danger:#f28b82;
  /* roles del pipeline (borde izquierdo + etiqueta) */
  --role-proposal:#8ab4f8; --role-critique:#c58af9; --role-vote:#fdd663;
  --role-chairman:#78d9ec; --role-target:#9ba4b8; --role-judge:#81c995;
  /* escala de score 0-5: gris → ámbar → rojo (nunca verde = "bien") */
  --score-low:#9ba4b8; --score-mid:#f0b429; --score-high:#f28b82; --score-max:#e5484d;
  /* geometría */
  --r-sm:6px; --r-md:8px; --r-lg:12px; --r-pill:999px;
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-5:24px; --sp-6:32px; --sp-7:48px;
  --focus:0 0 0 3px color-mix(in srgb,var(--accent) 45%,transparent);
  --shadow-1:0 1px 2px rgba(0,0,0,.4),0 2px 6px rgba(0,0,0,.3);
  --shadow-2:0 2px 6px rgba(0,0,0,.5),0 6px 16px rgba(0,0,0,.4);
}
:root[data-theme="light"] {
  --bg:#f8f9fa; --surface-1:#fff; --surface-2:#f1f3f4; --surface-3:#e8eaed;
  --border:#dadce0; --border-strong:#bdc1c6;
  --text-1:#202124; --text-2:#5f6368; --text-3:#5f6368;
  --accent:#1a73e8; --btn:#1a73e8; --btn-h:#1666d3;
  --success:#1e8e3e; --warning:#b06000; --danger:#d93025;
  --role-proposal:#1a73e8; --role-critique:#a142f4; --role-vote:#f9ab00; --role-chairman:#12a4af; --role-target:#5f6368; --role-judge:#1e8e3e;
  --score-low:#5f6368; --score-mid:#b06000; --score-high:#d93025; --score-max:#a50e0e;
}
```

Los nombres antiguos (`--fg`, `--muted`, `--faint`, `--surface`, `--surface2`, `--blue`…) se mantienen como alias durante la migración para no romper nada.

### 3.2 Tipografía

| Rol | Tamaño / interlínea | Peso | Uso |
|---|---|---|---|
| overline | 11 / 16, mayúsculas, tracking .6 px | 600 | etiquetas de sección, rol del evento |
| caption | 12 / 16 | 400-500 | meta, subtextos, labels de formulario |
| body-sm | 13 / 18 | 400 | tablas, filas de historial |
| body | 14 / 22 | 400 | prosa del stream, chat, descripciones |
| title | 16 / 24 | 500 | cabecera de tarjeta, goal |
| h1 | 20 / 28 | 500 | título de vista |
| kpi | 28 / 32, `tabular-nums` | 700 | números del dashboard |
| mono | 13 / 20 Roboto Mono | 400 | prompt enviado al target, IDs, modelos |

Se eliminan 10, 10.5, 12.5, 13.5, 15, 18 y 24.

### 3.3 Layout

**Shell.** Cabecera 56 px: logo + título de la vista + (si hay run en curso) chip "1 running" + toggle de tema. Rail 72 px con icono + etiqueta; al pie, GitHub. Bajo 820 px: nav inferior fija de 3 pestañas; FAB del chat sube 72 px.

**New run (dos modos en la misma pestaña, renombrada "Runs").**

```
┌ rail ┐ ┌──────────── 380px ─────────────┐ ┌──────────────── 1fr ────────────────────┐
│      │ │ 1 ATTACK          [council ▾]  │ │ RUN HEADER                              │
│ Runs │ │   descripción · How it works    │ │ goal · council · qwen → claude · 09:20  │
│ Stats│ │   ▸ Advanced (turns, borda…)    │ │ Completed · best 1/5 resisted   [Stop]  │
│ Hist │ │ 2 TARGET     [Local Ollama ▾]  │ ├─────────────────────────────────────────┤
│      │ │   URL · model · key             │ │ G1 1/5 · G2 0/5 · G3 …   (índice/chips) │
│      │ │ 3 BEHAVIOURS                    │ ├─────────────────────────────────────────┤
│      │ │   goal ó biblioteca (3 sel.)    │ │ ▾ Turn 1  1/5                2 proposals│
│      │ │ ▸ Council (solo attacks council)│ │   ┃ PROPOSAL qwen2.5:3b   prosa Roboto  │
│      │ │─────────────────────────────────│ │   ┃ BORDA  1. qwen2.5:3b ████ 2  ★      │
│      │ │ council · 1 goal → qwen2.5:1.5b │ │   ┃ CHAIRMAN → prompt enviado (mono)     │
│      │ │ [      Launch attack       ]    │ │   ┃ TARGET  prosa …           Read more │
│      │ └── pie sticky ──────────────────┘ │   ┃ JUDGE  1/5 resisted  rationale       │
└──────┘                                    └─────────────────────────────────────────┘
```

Estado vacío del panel derecho: "How a council run works" en 4 pasos con los colores de rol + botones "Launch" y "Open a past run". Sirve de leyenda.

**Statistics.** Fila de filtros con etiquetas + chips de ámbito activo. KPIs: `Goals attacked · N runs`, `ASR (best ≥ 5)`, `Jailbroken`, `Avg best score`. Distribución como barra apilada única con leyenda. Tres bloques de ASR en una rejilla de 2 columnas (attack | target; theme debajo a ancho completo) con `n/N` en la clave. Tabla de miembros a 720 px, ordenada, con barra de win rate.

**History.** Tabla con cabecera sticky en escritorio: Goal (truncado 1 línea, tooltip) · Attack · Target · Status · Outcome (pill de score con palabra) · Date. Filtros en una fila con etiquetas; chips de filtros activos; "Load more". Fila → abre la vista Run.

**Chat.** Panel 420×600, cabecera limpia (título, conversación, engranaje), ajustes en popover, Markdown básico, Stop durante streaming, hoja completa en móvil.

### 3.4 Componentes a unificar

- **Botón**: `primary`, `primary.danger`, `secondary` (borde), `ghost` (icono). Alturas 40 px (formulario) y 32 px (inline). `:focus-visible{box-shadow:var(--focus)}`, `:active{transform:translateY(1px)}`.
- **Input/select/textarea**: fondo `--surface-2`, borde `--border`, foco con anillo. Label con `for`.
- **Pill de score**: `score score-{low|mid|high|max}`, con texto "resisted / partial / jailbroken".
- **Pill de estado de ejecución**: `status status-{completed|running|error|cancelled}`.
- **Tarjeta**: `--surface-1`, borde `--border`, radio `--r-lg`, sombra `--shadow-1`. Cabecera de tarjeta 48 px.
- **Evento del stream**: borde izquierdo 3 px `--role-*`, overline con rol + modelo en mono, cuerpo en body.

---

## 4. Medidas de apoyo

**Contraste (ratio WCAG; AA normal ≥ 4.5, AA grande/UI ≥ 3)**

| Par | Oscuro | Claro | Veredicto |
|---|---|---|---|
| `--fg` sobre `--surface` | 14.3 | 16.1 | ok |
| `--muted` sobre `--surface` | 6.8 | 6.1 | ok |
| `--faint` sobre `--surface` (desc, barsub, empty, lib theme) | 3.8 | 3.7 | falla AA texto |
| `--accent` sobre `--surface2` (botones mini) | 7.6 | 4.1 | claro justo |
| blanco sobre `--btn` | 4.5 | 4.5 | justo |
| `--yellow` texto (fila ganadora Borda) | 11.5 | 1.7 | claro falla |
| pill `s3` amarillo sobre amarillo 22 % | 6.5 | 1.5 | claro falla |
| pill `s5` blanco sobre `--red` | 2.4 | 4.8 | oscuro falla |
| borde de input vs superficie | 1.25 | 1.37 | falla UI (≥ 3) |
| fondo de input vs tarjeta (oscuro) | 1.09 | 1.05 | invisible |

**Objetivos táctiles < 44 px a 390 px**: toggle de tema 18×36, cerrar chat 19×17, selector de proveedor 90×28, lista de chats 146×28, "+ New" 52×26, chips de sugerencia 316×37.

**Teclado**: Tab llega al rail (anillo por defecto del navegador, 1 px), pero las cabeceras de goal/turn, las filas de History y el cierre del modal por Escape no funcionan.

**Peso del formulario**: 9 controles visibles, 3 desplegables, 2408 px de alto interno con la biblioteca plegada.

---

## 5. Respuestas breves a las diez preguntas del brief

1. **IA y navegación.** Tres pestañas son pocas pero correctas si "New run" se convierte en "Runs" (configurar + ver). Falta la vista de detalle de run (H4). "Attacks" como catálogo es deseable en una fase posterior (el backlog ya lo contempla); hoy el modal "How this attack works" cubre el 70 %. El rail no comunica dónde estás (M5).
2. **Jerarquía y densidad.** Buena base, pero once tamaños de fuente, cinco radios y bordes casi invisibles la hacen parecer "casi GTI". Con la escala de §3 y bordes a 3:1 pasa a profesional.
3. **New run.** Agrupar en 3 pasos + Council condicional + pie sticky (H3, M12).
4. **Stream.** Se entiende el pipeline pero no el run. Prosa en Roboto, mono sólo en el prompt final, panel Borda como ranking con barras, cabecera de run, auto-colapso (H4, H7, M1, M8).
5. **Dashboard.** ASR con `n/N`, distribución apilada con leyenda, tabla acotada; filtros con chips de ámbito y sin el bug del filtro fantasma (H5, M2-M4).
6. **Chat.** Ubicación correcta; cabecera sobrecargada; falta Markdown, Stop y modo hoja en móvil (M11).
7. **Estados.** Faltan skeletons, toasts y un vacío que enseñe (M10). Estado de ejecución y resultado deben separarse (H2).
8. **Accesibilidad.** Contraste de `--faint` y bordes, `for` en labels, plegables por teclado, diálogo con Escape, `aria-current`, targets de 44 px (M6, M7).
9. **Responsive.** Sí, nav inferior; header que cede; sin scroll interno en History; chat como hoja (H6, M9, M11).
10. **Marca.** Coherente; se conserva íntegra. Añadir tokens semánticos y de rol, favicon por tema, y micro-interacciones (B4, B7).

---

## 6. Plan de implementación propuesto (pendiente de aprobación)

Rama `design/audit-2026-09`, commits a nombre del autor, sin firmas de IA. Mismo `standalone.html`, mismos endpoints y eventos.

| Fase | Contenido | Hallazgos | Esfuerzo |
|---|---|---|---|
| 1. Quick wins | Clic en History abre la vista; vocabulario de estado vs resultado; nav inferior móvil; chip de conexión sólo en vivo; prosa en Roboto; pie sticky con Launch; renombrado de variables en `/stats` | H1, H2, H6, H7, H8, H3 parcial, H5 | 2-3 h |
| 2. Sistema visual | Tokens y escalas de §3, componentes unificados, contraste, bordes, radios, foco visible, labels `for`, diálogo accesible | M5, M6, M7, B1-B4 | 3-4 h |
| 3. New run + Run | Formulario en 3 pasos, Council condicional, cabecera de run, índice de goals, auto-colapso, panel Borda, estado vacío didáctico | H3, H4, M1, M8, M10, M12 | 4-5 h |
| 4. Stats, History, Chat | Barras con n/N, distribución apilada, tabla de miembros, tabla de History, chat con popover/Markdown/Stop/hoja móvil | M2, M3, M4, M9, M11, B6, B7 | 4-5 h |

Cada fase termina con las mismas capturas (1440/1024/390, oscuro/claro) en `docs/design-audit/after/` para comparar.
