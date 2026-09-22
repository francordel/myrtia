# Prompt: sistema de diseño de Myrtia (para el agente de funcionalidad)

Eres el agente que implementa funcionalidad en Myrtia, una herramienta open-source de red teaming de LLMs. El front-end es un único fichero `frontend/standalone.html` (HTML + CSS + JS vanilla, sin build), servido por FastAPI desde `backend/myrtia/`. El diseño ya está definido e implementado; tu trabajo es añadir funcionalidad **sin romperlo**. Este documento es la referencia: todo lo que añadas debe usar estos tokens, componentes, helpers y reglas. Si algo que necesitas no existe aquí, extiende el sistema siguiendo su lógica y documenta la extensión al final de este fichero.

## 1. Identidad y tono

- Estética Google Threat Intelligence / Palantir: seria, geométrica, oscura por defecto con tema claro. Acento azul Google. Nada de "cyber" (candados, circuitos, neones).
- Texto en Roboto. Monospace (Roboto Mono) **sólo** para prompts literales, IDs y nombres de modelo. La prosa (respuestas del target, razonamientos del juez, propuestas) va en Roboto 14/1.6.
- Wordmark en cabecera: `h1 b` en Montserrat 300, mayúsculas, `letter-spacing:.28em`. No lo toques.
- Logo: hoja de mirto (`/assets/icon-dark.png` en oscuro, `icon-light.png` en claro). No cambies el logo.
- Nada de estilos inline en HTML nuevo; todo va en el bloque `<style>` con clases.

## 2. Tokens (`:root` y `:root[data-theme="light"]`)

Usa siempre variables, nunca colores literales.

| Grupo | Tokens |
|---|---|
| Superficies | `--bg`, `--surface-1` (tarjetas), `--surface-2` (inputs, cabeceras de turno, eventos), `--surface-3` (hover, pistas de barras) |
| Bordes | `--border`, `--border-strong` (hover) |
| Texto | `--text-1` (principal), `--text-2` (secundario, ≥ 6:1), `--text-3` (terciario, ≥ 4.5:1). No uses `--text-3` por debajo de 12 px |
| Marca | `--accent`, `--accent-bg` (fondo de activo/selección), `--btn`, `--btn-h`, `--btn-fg` |
| Semántica UI | `--info`, `--success`, `--warning`, `--danger` |
| Roles del pipeline | `--role-proposal` (azul), `--role-critique` (morado), `--role-vote` (amarillo), `--role-chairman` (cian), `--role-target` (gris), `--role-judge` (verde) |
| Escala de score 0-5 | `--score-low` (0-2, gris), `--score-mid` (3-4, ámbar), `--score-high` (4), `--score-max` (5, rojo sólido con `--score-max-fg`) |
| Geometría | radios `--r-sm` 6, `--r-md` 8, `--r-lg` 12, `--r-pill`; espaciado `--sp-1..7` = 4, 8, 12, 16, 24, 32, 48 px |
| Otros | `--focus` (anillo de foco), `--shadow-1`, `--shadow-2`, `--header-h` 56, `--rail-w` 72 |

Los nombres antiguos (`--fg`, `--muted`, `--faint`, `--surface`, `--surface2`, `--blue`, `--red`, `--yellow`, `--green`, `--purple`, `--cyan`) existen como alias; no los uses en código nuevo.

**Regla de color más importante:** el verde nunca significa "el proceso terminó". El estado de ejecución de un run (`Completed`, `Running`, `Error`, `Cancelled`) usa `.status` en neutro/ámbar/rojo/gris. El resultado del ataque usa `.score` con la escala gris → ámbar → rojo y la palabra `resisted | partial | jailbroken`. Son dos dimensiones distintas y siempre se muestran por separado.

## 3. Tipografía y escala

| Rol | Uso | Clase / regla |
|---|---|---|
| 11 px 600 mayúsculas, tracking .6 px | etiquetas de sección, rol del evento | `.overline`, `.ev .role`, `.goalbar .tag` |
| 12 px | meta, subtextos, labels de formulario | `.caption`, `label`, `.desc` |
| 13 px | tablas, filas, botones secundarios | `table.tab`, `.runrow .c`, `.btn-outline` |
| 14 px / 1.55-1.6 | prosa, chat, cuerpo | `body`, `.ev .body`, `.cmsg` |
| 16 px 500 | títulos de tarjeta, goal | `.card-h`, `.runhead .t`, `.empty h3` |
| 28 px 700 tabular | KPIs | `.statnum` |
| 13 px mono | prompt enviado, ids, modelos | `.mono`, `.ev .body.mono` |

No introduzcas otros tamaños (10, 10.5, 12.5, 13.5, 15, 18, 24 están prohibidos).

## 4. Shell y navegación

- `header` (56 px, sticky): logo + wordmark + título de vista (`#viewTitle`), `#liveChip` ("N running", sólo visible con runs activos), toggle de tema `#theme`.
- `nav.rail` (72 px, fijo a la izquierda): botones `.railbtn[data-view]` con icono SVG de 22 px + etiqueta de 11 px, `aria-current="page"` en el activo, punto `.badge` cuando hay runs en curso. Bajo 820 px el mismo `nav` pasa a barra inferior de 64 px (no dupliques la navegación).
- Vistas: `div.view#view-*` dentro de `main`, sólo una visible (`hidden`). Cambia de vista con `showView(id)` y registra el título en `VIEW_TITLE`. Para añadir una vista: nuevo `.view`, nuevo `.railbtn[data-view]` con icono, entrada en `VIEW_TITLE`, y la carga de datos dentro de `showView`.
- Breakpoints: 1100 px (rejillas a 1-2 columnas, columna lateral 340 px) y 820 px (una columna, nav inferior, chat a pantalla completa, FAB a 80 px del borde).

## 5. Componentes (clases a reutilizar)

- **Tarjeta**: `.card` + `.card-h` (48 px, título 16 px y `.caption` a la derecha) + `.card-b`.
- **Formulario**: secciones `.fsec` con `.fsec-h` (`.n` numerado, `h2`, `.caption` resumen). `label[for]` + `input/select/textarea` (40 px de alto, fondo `--surface-2`). Ayudas en `.desc` o `label .hint`. Plegables con `details.adv > summary`. Casillas con `.adv-row.bool`. Pie fijo `.launch-foot` con `#launchSummary` y el botón primario. Al añadir un campo, ponlo en la sección semántica correcta (1 Attack, 2 Target, 3 Behaviours, 4 Council) y actualiza `updSummary()` si afecta al resumen. La sección Council (`#councilSec`) sólo se muestra para plugins council (`isCouncil(p)`).
- **Botones**: `button.primary` (44 px, ancho completo; `.danger` para destructivos), `.btn-outline` (32 px, secundario; `.danger`), `.mini` (acciones dentro de listas), `.icon-btn` (redondo 40 px, cabecera), `.chat-h .ib` (40 px, icono en el chat). Todos con `:focus-visible` por `--focus` y `:active` con desplazamiento de 1 px.
- **Pills**: `.status.{completed|running|error|cancelled|queued|interrupted}` vía `statusPill(st)`; `.score.{low|mid|high|max}` vía `scorePill(sc, prefijo)`; `.tagpill` para temas; `.chip` (`.live`, `.run`, `.err`, `.ok`, `.btn`) para indicadores de cabecera; `.gchip` para el índice de goals; `.fchip` para filtros activos en Statistics.
- **Stream**: `.goal-sec` > `button.goalbar` (+ `.goal-turns`) > `.card.turn` > `button.turn-h` + `.turn-body` > `.ev.{proposal|critique|vote|chairman|target|judge|log}` con `.lab` (`.role` + `.who`) y `.body` (`.mono` para prompts, `.clamp` + `.morebtn` si > 320 caracteres). El panel Borda es `.ev.vote` con `.rank` (filas `.r`, `.win`, barra `.bar`) y `.critlist`. Para un tipo de evento nuevo: añade su rama en `evNode()`, su etiqueta en `LABELS`, y si es un rol nuevo, un token `--role-*` y las reglas `.ev.<rol>`.
- **Cabecera de run**: `#runHead` (`.runhead`): `.t` título, `.m` meta, `.acts` botones, `.pills` (estado, mejor score, contadores, `#goalIdx`). Se alimenta del objeto `RUN` (`id, spec, status, created_at, error`) y de `events`; se repinta con `renderRunHead()`.
- **Estadísticas**: bloques con `.chartlbl` (`.overline` + `.caption`), KPIs `.statgrid > .statbox` (`.hot` para el principal), distribución `.stack` + `.stack-leg`, barras `.bars > .bar` generadas por `asrBars(rows)` (fila = clave + `n/N` + pista con marca de avg + valor), tablas `table.tab` (máx. 760 px, números `.num` alineados a la derecha, barra `.wr`).
- **Historial**: `.runtab` con `.runhdr` (cabecera ordenable) y `.runrow` (grid de 6 columnas en escritorio, 2 en móvil; celdas `.c`, `.keep` para las que sobreviven en móvil, `.hide-md` para las que caen a 1100 px). Fila = `role="button" tabindex="0"` y abre con `openRun(id, meta)`.
- **Vacíos, carga, error**: `.empty` (título + párrafo + acciones `.acts`; el del stream enseña el pipeline `.pipe` y la leyenda `.legend`), `.skel` para skeletons, `.none` para "sin datos" en un bloque, `toast(msg, "info"|"ok"|"err", {label, fn})` para errores y confirmaciones. No uses `alert()` ni textos de error en chips de cabecera.
- **Diálogo**: `<dialog>` nativo (`showModal()` / `close()`), con `.modal-h`, `.modal-x`, `.modal-desc`, `.modal-steps`. Escape y foco los da el navegador.
- **Chat**: `#chatPanel` (420×600, hoja completa en móvil) con `.chat-h` (título, `#chatList`, `+`, engranaje `#chatGear`, cerrar), ajustes en `#chatSettings.open`, mensajes `.cmsg.{user|bot|err}`, respuestas del bot renderizadas con `md()` (Markdown mínimo, escapado previo), `#chatIn.busy` muestra `#chatStop` (AbortController).

## 6. Helpers JS que debes reutilizar

`$(id)`, `API()` (base URL sin barra final), `esc(s)` (**obligatorio** antes de meter cualquier texto de la API o del usuario en `innerHTML`), `shortModel(m)`, `scorePill`, `scoreCls`, `scoreWord`, `statusPill`, `STATUS_LABEL`, `toast`, `showView`, `openRun(id, meta)`, `connectRun(id)`, `render()`, `renderRunHead()`, `renderEmpty()`, `loadHistory()`, `loadStats()`, `loadPlugins()`, `updSummary()`, `fmtTime(ts)`, `md(text)`, `keyGet/keySet` (claves por proveedor en localStorage).

Estado que se conserva entre re-renders del stream (no lo rompas): `goalOpen` (Map goal → abierto), `collapsedTurns`, `expandedEv`. Por defecto sólo el último goal está abierto. El stream hace stick-to-bottom mientras `RUN.status === "running"` y muestra `#jumpLive` si el usuario se ha desplazado hacia arriba.

## 7. Contrato con el backend (no lo cambies desde el front)

Endpoints: `GET /plugins`, `GET /behaviors?theme&q`, `POST /runs`, `GET /runs?q&theme&attack&result&min_score`, `GET /runs/{id}`, `POST /runs/{id}/stop`, `GET /stats?attack&target`, `POST /chat/stream` (SSE `data: {delta|error}`), `WS /runs/{id}/events`. Eventos: `run.started`, `goal.started`, `turn.started`, `proposal.created`, `critique.created`, `vote.aggregated`, `chairman.synthesized`, `target.responded`, `judge.scored`, `run.finished`, `log.*`. Si añades un endpoint o evento, añade también su render siguiendo §5.

Claves de `localStorage` en uso: `myrtia-theme`, `myrtia-key-<provider>`, `myrtia-chats`.

## 8. Accesibilidad y responsive (obligatorio en todo lo nuevo)

- Cada `input/select/textarea` con `label for` o `aria-label`.
- Todo lo que se pliega es un `button` con `aria-expanded`; nada de `div onclick`.
- Objetivos táctiles ≥ 40 px de alto en móvil (44 en botones primarios).
- Contraste: texto ≥ 4.5:1 sobre su fondo, bordes y UI ≥ 3:1. Verifica en los dos temas.
- Sin scroll interno en tarjetas de página (la única excepción es la lista de la biblioteca de comportamientos, `.liblist`).
- Comprueba a 1440, 1024 y 390 px, oscuro y claro.

## 9. Verificación antes de dar por terminado un cambio de UI

1. Carga `http://127.0.0.1:8000/` con Playwright (está en `.venv`) y confirma **cero** errores o warnings de consola en las tres vistas.
2. Haz capturas a 1440, 1024 y 390 px en oscuro y claro y guárdalas en `docs/design-audit/after/` con el mismo prefijo numérico que las existentes (01 run, 03 history, 06 stats, 07 chat, 15-19 móvil, 23-24 stream multi-goal). El script de referencia está en el historial de la auditoría: navega, cambia de vista, abre el chat y el diálogo, pulsa una fila de History y comprueba que `#view-run` deja de estar `hidden`.
3. Si tocas el formulario, comprueba que `#launch` está dentro del viewport al aterrizar a 1440×900.
4. Si tocas el stream, abre el run de 5 goals y comprueba que sólo el último goal está abierto y que `#goalIdx` tiene 5 chips.

## 10. Lo que NO debes reintroducir

- Chips "disconnected" / "idle" en la cabecera.
- Prosa en monospace.
- Verde para "succeeded" / "completed".
- Scroll interno en la tarjeta del formulario o en la lista de History.
- Tamaños de fuente fuera de la escala, colores literales, estilos inline.
- `innerHTML` con texto sin `esc()`.
- Secciones Council visibles en ataques sin council.

---

## Extensiones registradas

(Añade aquí cada componente, token o helper nuevo con una línea: qué es, dónde está y para qué se usa.)
