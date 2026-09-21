# Myrtia — Mapa de UI y Observabilidad (reconocimiento de PentAGI)

Documento de reconocimiento. Analiza el repo de referencia **PentAGI**
(`/Users/franciscojosecortesdelgado/Documents/GitHub/pentagi-reference`, solo lectura)
para extraer patrones reutilizables en **Myrtia** (framework open-source de red
teaming de IA/LLM con front-end). No se copia código; se describen mecanismos y decisiones.

Objetivo prioritario de Myrtia: **"ver cómo se activan los agentes" en vivo**, con
human-in-the-loop y un stack de observabilidad. Scope: red teaming de LLM (NO pentest de red).

Nota sobre alcance de PentAGI: su producto es un agente de pentesting autónomo. Nos
interesa el **patrón de UI en vivo + observabilidad**, no su dominio (herramientas de red,
terminal en contenedores, etc.). Varios conceptos se mapean casi 1:1 al red teaming de LLM;
otros hay que simplificarlos o descartarlos.

---

## TAREA 1 — UI React

### 1.1 Montaje de la UI (framework / bundler / build)

- **Framework**: React 19 + TypeScript, SPA.
- **Bundler / dev server**: **Vite 8** con `@vitejs/plugin-react-swc` (SWC, no Babel).
  - `vite-tsconfig-paths` (alias `@` → `src`), `vite-plugin-html` para inyectar título.
  - Build con code-splitting manual muy cuidado (`rollupOptions.output.codeSplitting.groups`):
    chunks separados para `react-vendor`, `apollo-client` (`@apollo/client`, `graphql`,
    `graphql-ws`), `radix-ui`, `terminal` (xterm), `charts` (recharts), `markdown`, `tiptap`,
    `pdf`, `marked`. Terser con `drop_console` en producción.
  - Dev server sirve por HTTP o HTTPS (autogenera certs), y **proxya** `/api/v1` (HTTP) y
    `/api/v1/graphql` (WS/WSS) al backend vía `VITE_API_URL`. `vite preview` replica el proxy.
- **UI kit**: **Radix UI primitives + patrón shadcn/ui** (`components.json`, `components/ui/*`),
  Tailwind CSS 4 (`@tailwindcss/postcss`), `class-variance-authority`, `clsx`, `tailwind-merge`,
  iconos `lucide-react`, animaciones `motion`, toasts `sonner`, tablas `@tanstack/react-table`
  + `@tanstack/react-virtual` (virtualización de listas largas de logs).
- **Formularios**: `react-hook-form` + `zod` (`@hookform/resolvers`).
- **Routing**: `react-router-dom` v7. Estructura por dominios en `src/features/*`
  (flows, authentication, knowledges, resources, templates) y providers de contexto en
  `src/providers/*`.
- **Otros**: `@xterm/xterm` (terminal en vivo), `recharts` (dashboards), `@tiptap/*` (editor
  markdown WYSIWYG), `@react-pdf/renderer` + `marked` (export de informes a PDF),
  `react-markdown` + `rehype/remark` (render de mensajes), `react-diff-viewer-continued`.

### 1.2 Comunicación con el backend: GraphQL + WebSocket subscriptions

- **Sí es GraphQL** (backend gqlgen; esquema en `backend/pkg/graph/schema.graphqls`).
  El front usa **Apollo Client 4** (`@apollo/client`).
- **Codegen tipado**: `graphql-codegen` (`typescript-operations` + `typed-document-node`)
  genera `src/graphql/types.ts` a partir del `.graphqls` del backend → documentos tipados
  (`FlowDocument`, `AgentLogAddedDocument`, etc.) y hooks tipados. Escalares custom mapeados
  (`Map` → `Record<string,unknown>`, `Time` → `string`).
- **Transporte dual (clave del "tiempo real")**, en `src/lib/apollo.ts`:
  - `HttpLink` para queries/mutations.
  - `GraphQLWsLink` (paquete `graphql-ws`) para **subscriptions** sobre WebSocket.
  - `split(isSubscriptionOperation, wsLink, httpLink)` enruta cada operación al transporte
    correcto según sea `subscription` o no.
  - WS con reconexión robusta: `retryAttempts: Infinity`, backoff exponencial con jitter
    (evita thundering-herd al reiniciar el backend), `lazy: true` (el socket solo abre en la
    primera subscription). Al **reconectar** hace `refetchObservableQueries()` porque las
    subscriptions son delta-only (el server no reenvía eventos perdidos) y dispara un evento
    `ws:reconnected` para que los datos hidratados por REST se refresquen.
  - Manejo de auth: errores GraphQL/red 401/403 disparan `auth:refresh` global.
- **Cadena de links Apollo** (orden significativo):
  `errorLink → subscriptionCacheLink → streamingLink → transportLink(split)`.
  - **`subscriptionCacheLink`**: intercepta cada subscription entrante y **actualiza la
    `InMemoryCache` automáticamente** según convención de nombres. Un mapa
    `subscriptionToCacheFieldMap` liga cada evento (`taskCreated`, `agentLogAdded`,
    `toolCallLogAdded`, `assistantLogUpdated`, `flowUpdated`, ...) con su campo de query
    (`tasks`, `agentLogs`, `toolCallLogs`, ...). El sufijo del nombre (`...Created` /
    `...Updated` / `...Deleted` / `...Added`) decide la estrategia (prepend, replace, remove,
    append). Esto significa que **la UI no tiene que gestionar manualmente el estado en vivo**:
    llega el evento y la lista correspondiente se actualiza sola. Patrón muy reutilizable.
  - **`streamingLink`**: maneja **streaming token-a-token** de las respuestas del LLM
    (`assistantLogUpdated` con flag `appendPart`). Acumula fragmentos en una `LRUCache`, hace
    **throttling a ~50 ms** para no re-renderizar en cada token, y al llegar el mensaje final
    reemplaza el acumulado. Directamente aplicable a mostrar respuestas del modelo atacado
    "escribiéndose" en vivo.
  - **`InMemoryCache` typePolicies**: la mayoría de listas por-flow usan `keyArgs: ['flowId']`
    y `merge: replace`. Detalle a imitar: campos que llegan vacíos en la query de lista y
    completos en la de detalle no deben pisar (`content merge`).

Esquema GraphQL relevante (raíces en `schema.graphqls`):
- **Query**: `flows`, `flow(flowId)`, `tasks`, `agentLogs`, `searchLogs`, `toolCallLogs`,
  `messageLogs`, `assistantLogs`, `terminalLogs`, `screenshots`, además de amplias
  estadísticas (`usageStats*`, `toolcallsStats*`, `flowsStats*`).
- **Mutation**: `createFlow`, `putUserInput`, `stopFlow`, `finishFlow`, `createAssistant`,
  `callAssistant`, `stopAssistant`, gestión de providers/prompts/tokens/templates/knowledge.
- **Subscription**: familia completa de eventos en vivo — `flowCreated/Updated/Deleted`,
  `taskCreated/Updated`, `agentLogAdded`, `toolCallLogAdded/Updated`, `messageLogAdded/Updated`,
  `assistantLogAdded/Updated`, `searchLogAdded`, `terminalLogAdded`, `screenshotAdded`,
  `vectorStoreLogAdded`, más eventos de providers/tokens/templates/resources.

### 1.3 Flujo human-in-the-loop (cómo se steerea al agente)

**Importante**: PentAGI **no implementa** un gate de aprobar/denegar cada acción sensible
del agente antes de ejecutarla. Su HITL es de tipo **"steering" conversacional**, no
"approval gating" por acción. Concretamente:

- Dos modos, en `FlowCentralTabs` (`features/flows/flow-central-tabs.tsx`), pestañas:
  - **Automation**: el agente ejecuta el flujo de forma autónoma; el operador puede inyectar
    input en cualquier momento con la mutation `putUserInput(flowId, input, ...)` para
    redirigir la investigación, y `stopFlow` / `finishFlow` para cortar o cerrar.
  - **Assistant**: back-and-forth paso a paso (chat). `createAssistant` / `callAssistant`
    con un toggle **"Use Agents"** (`useAgents: Boolean!`) que decide si el asistente delega
    en sub-agentes especializados. `stopAssistant` para interrumpir.
  - **Dashboard**: métricas del flow (ver 1.4).
- El estado y las acciones viven en `providers/flow-provider.tsx` (contexto `FlowProvider`):
  expone `submitAutomationMessage`, `submitAssistantMessage`, `stopAutomation`,
  `stopAssistant`, `putUserInput`, la lista de `assistants`, `assistantLogs`, y se suscribe a
  todos los eventos del flow.
- `ConfirmationDialog` (`components/shared/confirmation-dialog.tsx`) existe, pero se usa para
  confirmaciones de **UI destructiva** (borrar assistant, reemplazar plantilla, sobrescribir
  ficheros), **no** como aprobación de acciones del agente.

**Implicación para Myrtia**: si queremos un HITL de "aprobar/denegar cada acción
sensible" (p.ej. antes de lanzar un prompt de ataque a un modelo de producción, o antes de
escalar a un jailbreak concreto), **hay que diseñarlo nosotros**, no está en PentAGI. El
patrón a añadir sería: el backend emite un evento de "acción pendiente" (nuevo estado tipo
`PENDING_APPROVAL` en el log/toolcall + subscription), la UI lo pinta con botones
Approve/Deny, y una mutation `resolveApproval(id, decision)` desbloquea al agente. El
transporte (subscriptions + cache auto-update por convención de nombres) de PentAGI soporta
esto perfectamente; solo falta el estado de "gate". Lo que PentAGI sí nos da gratis: el canal
en vivo, el streaming y el mecanismo de steering/stop.

### 1.4 Vista en vivo del "flow" (cómo se visualiza el progreso)

Todo cuelga de `features/flows/*`, alimentado por `FlowProvider` y las subscriptions.
Cada panel es una lista virtualizada con auto-scroll al último evento
(`hooks/use-auto-scroll.ts`, `use-element-virtual-list.ts`) y búsqueda/filtrado con debounce:

- **agents/** (`flow-agents.tsx`, `flow-agent.tsx`, `flow-agent-icon.tsx`): stream de
  `agentLogs` — qué agente/sub-agente actúa, con filtro por task/subtask. Icono por proveedor
  (`components/icons/*`: anthropic, openai, gemini, bedrock, ollama, deepseek, qwen, ...).
- **tasks/** (`flow-tasks.tsx`, `flow-task.tsx`, `flow-subtask.tsx`, `flow-task-status-icon.tsx`):
  árbol tasks → subtasks con iconos de estado en vivo (`taskCreated/Updated`).
- **tools/** (`flow-tools.tsx`, `flow-tool.tsx`) y **messages/**, **screenshots/**,
  **terminal/** (xterm en vivo vía `terminalLogAdded`), **vector-stores/**: cada tipo de
  actividad del agente tiene su panel, todos hidratados por subscription.
- **dashboard/** (`flow-dashboard.tsx`, `flow-dashboard-overview.tsx` + `components/dashboard/*`
  con recharts): métricas del flow (uso de tokens, toolcalls, tiempos) directamente desde las
  queries `*StatsByFlow`.
- Estado global del flow: `flow-status-badge.tsx` / `flow-status-icon.tsx` reflejan
  `flowStatus` (running/finished/failed…) actualizado por `flowUpdated`.

Patrón general reutilizable: **una subscription por tipo de evento → auto-update de cache por
convención de nombres → panel virtualizado con auto-scroll**. "Ver activarse los agentes" =
paneles agents/tasks/tools/messages actualizándose en tiempo real.

### 1.5 Dependencias npm relevantes y riesgo de licencia (GPL/AGPL)

Gestor: **pnpm**. `frontend/LICENSE` del propio PentAGI es **MIT** (el EULA/comercial aplica al
producto completo, pero el front es MIT).

Dependencias clave (todas permisivas salvo lo indicado):
- Núcleo tiempo real: `@apollo/client` (MIT), `graphql` (MIT), `graphql-ws` (MIT), `ws` (MIT).
- UI: `@radix-ui/*` (MIT), `tailwindcss` (MIT), `lucide-react` (ISC), `class-variance-authority`
  (Apache-2.0), `clsx` (MIT), `sonner` (MIT), `cmdk` (MIT), `motion` (MIT).
- Datos/tablas/virtualización: `@tanstack/react-table`, `@tanstack/react-virtual` (MIT).
- Terminal: `@xterm/*` (MIT). Charts: `recharts` (MIT). Markdown: `react-markdown`,
  `remark-gfm`, `rehype-*`, `marked`, `lowlight`, `highlight.js` (MIT/BSD). PDF:
  `@react-pdf/renderer` (MIT). Forms: `react-hook-form` (MIT), `zod` (MIT).
- Build/dev: `vite`, `@vitejs/plugin-react-swc`, `typescript`, `eslint`, `prettier`,
  `vitest`, `@playwright/test`, `graphql-codegen` (MIT/Apache-2.0).

**Riesgo GPL/AGPL — a VERIFICAR antes de fijar dependencias**:
- `react-diff-viewer-continued`: **verificar** (los diff-viewers a veces arrastran licencias
  mixtas; confirmar que es MIT).
- `github-slugger`, `use-debounce`, `react-day-picker`, `react-resizable-panels`,
  `react-textarea-autosize`, `tw-animate-css`, `date-fns`, `lru-cache`, `axios`: se esperan
  permisivas (MIT/ISC/Apache) pero **verificar** en su `package.json`/repo antes de vendorizar.
- No se ha detectado ninguna dependencia **GPL/AGPL directa** en el `package.json` del front.
- **Ojo con el backend/stack, no con npm**: la observabilidad sí incluye componentes con
  copyleft/licencias no-Apache (ver Tarea 2). El front en sí parece limpio.

Recomendación: correr un `license-checker` / `pnpm licenses list` sobre el árbol resuelto y
fallar el CI ante GPL/AGPL/SSPL. Marcar como "verificar" cualquier paquete sin licencia clara.

---

## TAREA 2 — Observabilidad

PentAGI separa observabilidad en **dos planos** con dos compose distintos:

1. **Plano LLM/agente** → **Langfuse** (`docker-compose-langfuse.yml`): trazas de LLM
   (prompts, respuestas, tokens, coste, latencia por agente/paso).
2. **Plano infra/servicio** → **stack OTel/Grafana** (`docker-compose-observability.yml`):
   métricas, logs y trazas distribuidas del sistema.

### 2.1 Langfuse (trazas del LLM: prompts, respuestas, tokens, latencia por agente/paso)

- **Instrumentación desde el backend Go**, no es auto-mágica: `backend/pkg/observability/`
  contiene un cliente Langfuse propio y completo:
  - `lfclient.go`: `LangfuseClient` (interfaz con `API()`, `Observer()`, `Shutdown`,
    `ForceFlush`) — cliente HTTP con cola de ingesta batched (`DefaultQueueSize`,
    `DefaultObservationInterval` 10 s, reintentos).
  - `langfuse/` (SDK propio): modela la jerarquía de observaciones de Langfuse —
    `trace.go`, `span.go`, `generation.go` (llamadas al LLM), `event.go`, `observation.go`,
    `score.go`/`evaluator.go` (evaluación), `tool.go`, `agent.go`, `chain.go`, `guardrail.go`,
    `embedding.go`, `retriever.go`. `observer.go`/`context.go` propagan el trace por el
    `context.Context` de Go, con `noop.go` para cuando está desactivado.
  - `langfuse/api/`: cliente REST generado (Fern) contra toda la API de Langfuse (ingestion,
    traces, observations, scores, sessions, prompts, datasets, media...).
- Se activa por env (`.env.example`): `LANGFUSE_BASE_URL`, `LANGFUSE_PROJECT_ID`,
  `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. Si faltan, el cliente entra en modo noop.
- **Qué muestra**: cada paso del agente se emite como trace → spans/generations, con prompt de
  entrada, respuesta, modelo, tokens, coste y latencia; los toolcalls como spans de tool; se
  pueden adjuntar scores (útil para Myrtia: puntuar éxito de un jailbreak / ASR).
- **Stack de Langfuse self-hosted** (`docker-compose-langfuse.yml`): `langfuse-web` +
  `langfuse-worker` (imagen `langfuse/langfuse:3`), con **postgres 16**, **clickhouse 24**,
  **redis 7** y **minio** (S3 para blobs de eventos/media). Es un stack pesado.
  - **Licencia — VERIFICAR/EVITAR**: Langfuse es mayormente MIT, **pero** algunas features
    "enterprise" viven bajo licencia comercial/EE. Para Myrtia open-source, usar solo el
    core OSS y verificar que no dependemos de módulos EE.

### 2.2 Grafana (dashboards) + VictoriaMetrics (métricas)

- **VictoriaMetrics** (`victoriametrics/victoria-metrics:v1.108.1`): TSDB compatible
  Prometheus (`remote_write` en `:8428/api/v1/write`). Recibe métricas del OTel Collector.
- **Grafana** (`grafana/grafana:11.4.0`): provisioning declarativo en
  `observability/grafana/config/provisioning/`:
  - **datasources** (`datasource.yml`): VictoriaMetrics (tipo prometheus), Jaeger y Loki, con
    correlación cruzada configurada — Jaeger `tracesToLogs` → Loki, y Loki `derivedFields`
    (`trace_id`) → Jaeger ("Trace for this log"). `nodeGraph` de Jaeger habilitado.
  - **dashboards** provisionados (`observability/grafana/dashboards/`): `home.json`,
    `components/pentagi_service.json` (métricas de la app), `components/victoriametrics.json`,
    y de servidor `node_exporter_full.json`, `docker_containers.json`, `docker_engine.json`.
- **Métricas expuestas** (via scrape del OTel Collector, ver 2.4): `node-exporter` (host),
  `cadvisor` (contenedores docker), docker-engine, clickhouse, jaeger, loki, pgvector
  (`pgexporter`), y las métricas propias de la app (`pentagi_service`) emitidas por OTel.

### 2.3 Jaeger (tracing distribuido), Loki (logs), OpenTelemetry (recolección)

- **OpenTelemetry Collector** (`otel/opentelemetry-collector-contrib:0.116.1`) es el hub
  central. Config en `observability/otel/config.yml`:
  - **receivers**: `otlp` (gRPC `:8148`, HTTP `:4318`) — el backend envía aquí; más
    `prometheus` (scrapea node-exporter, clickhouse, jaeger, loki, pgexporter) y
    `prometheus/docker` (docker-engine, cadvisor).
  - **pipelines**:
    - `traces`: otlp → batch → **Jaeger** (`otlp` a `jaeger:4317`).
    - `logs`: otlp → attributes+batch → **Loki** (`otlphttp` a `http://loki:3100/otlp`).
    - `metrics`: otlp+prometheus → batch → **VictoriaMetrics** (`prometheusremotewrite`).
- **Jaeger** (`jaegertracing/all-in-one:1.56.0`): trazas distribuidas, con **almacenamiento en
  ClickHouse** vía plugin gRPC (`jaeger-clickhouse` binario en `observability/jaeger/bin`,
  backend `clickstore` = clickhouse 24). UI en `:16686`.
- **Loki** (`grafana/loki:3.3.2`): agregación de logs, recibe OTLP del collector, se consulta
  desde Grafana. Correlación log↔trace por `trace_id`.
- El backend Go usa OTel SDK nativo (`backend/pkg/observability/obs.go`, `otelclient.go`,
  `collector.go`): traces/metrics/logs con `semconv`, propagación de contexto, y exporta al
  Collector según `OTEL_HOST` (`.env`). Hay también `profiling/profiling.go` (pprof).

### 2.4 Cómo se levanta y mínimo para "ver los agentes en vivo"

- Tres compose independientes conectados por **redes docker externas compartidas**:
  `pentagi-network`, `observability-network`, `langfuse-network`. El OTel Collector se une a
  las tres (así llega a Jaeger/Loki/VM en su red y recibe del backend en la de la app).
- Orden: crear las redes externas → `docker-compose.yml` (app + postgres/pgvector) →
  `docker-compose-langfuse.yml` (opcional, LLM tracing) → `docker-compose-observability.yml`
  (opcional, infra). Puertos expuestos solo en loopback por defecto
  (`GRAFANA_LISTEN_IP:-127.0.0.1`, etc.).
- **Mínimo para "ver los agentes activarse en vivo"**: NO hace falta el stack de infra
  (Grafana/VM/Jaeger/Loki/cadvisor/node-exporter). Basta con:
  1. Backend + **GraphQL subscriptions sobre WebSocket** (esto es lo que pinta la UI en vivo;
     la observabilidad de infra es ortogonal).
  2. **Langfuse** (opcional pero muy recomendable) para inspeccionar prompt/respuesta/tokens/
     latencia por paso — es el "microscopio" del comportamiento del LLM, justo lo que un
     framework de red teaming necesita.
  El resto (Grafana/VM/Jaeger/Loki) es para salud del sistema, no para el live view.

---

## Recomendación: stack mínimo viable para Myrtia

**Reusar como patrón (alto valor, bajo coste):**

1. **Transporte GraphQL + subscriptions vía `graphql-ws`** con Apollo Client 4 y `split()`
   http/ws. Es el corazón del live view y está muy pulido.
2. **Auto-actualización de cache por convención de nombres de subscription**
   (`...Added/Created/Updated/Deleted` → estrategia de cache). Elimina casi todo el manejo
   manual de estado en tiempo real. Copiar este patrón (no el código).
3. **`streamingLink` con acumulación en LRU + throttling** para render token-a-token de
   respuestas del modelo. Directamente aplicable a mostrar la salida del LLM atacado en vivo.
4. **Codegen tipado** (`graphql-codegen` contra el schema del backend) para tipos y documentos
   end-to-end.
5. **UI kit Radix + shadcn/ui + Tailwind + lucide + sonner**, listas **virtualizadas con
   auto-scroll** para los streams de eventos (agents/tasks/tools/messages). Todo MIT.
6. **Modelo de paneles por tipo de evento** dentro de una vista de "run/flow": en Myrtia
   serían p.ej. Attempts, Turns/Prompts, Model responses, Judge/Score, Findings.
7. **Langfuse** para trazas del LLM (prompt, respuesta, tokens, latencia, coste, **scores**).
   Los scores encajan perfecto con métricas de red teaming (ASR, éxito de jailbreak).
8. **OTel Collector como único punto de salida** de traces/logs/metrics, si algún día se quiere
   infra observability, para no acoplar el backend a Jaeger/Loki/VM concretos.

**Simplificar / posponer:**

- **HITL de aprobación por acción**: PentAGI NO lo tiene (solo steering). Diseñarlo nosotros
  como estado `PENDING_APPROVAL` + subscription + mutation `resolveApproval` sobre el mismo
  transporte. Prioritario para Myrtia si el scope incluye ataques a sistemas reales.
- **Descartar del dominio de PentAGI**: terminal xterm en contenedores, file manager de
  contenedor, herramientas de pentest de red, screenshots de navegador — no aplican al red
  teaming de LLM (o se reducen mucho).
- **Stack de infra completo (Grafana + VictoriaMetrics + Jaeger + Loki + cadvisor +
  node-exporter + ClickHouse)**: dejarlo como opt-in para v2. No es necesario para el live
  view ni para el MVP. Levantar Jaeger con ClickHouse + plugin es especialmente pesado.
- **Langfuse self-hosted (postgres+clickhouse+redis+minio)**: pesado. Para el MVP, permitir
  apuntar a **Langfuse Cloud** o hacerlo opt-in; o empezar con solo los paneles GraphQL en vivo
  y añadir Langfuse cuando haga falta análisis histórico.

**Verificar licencias antes de fijar:**

- Front npm: sin GPL/AGPL directo detectado; **verificar** `react-diff-viewer-continued` y los
  utilitarios menores; añadir gate de licencias en CI (`pnpm licenses list`, fallar ante
  GPL/AGPL/SSPL).
- Langfuse: usar solo core OSS (MIT), **evitar** módulos enterprise (EE).
- Stack observability: imágenes Grafana/Loki (AGPL en algunas versiones de productos Grafana
  Labs — **verificar** la versión concreta si se redistribuye), VictoriaMetrics (Apache-2.0),
  Jaeger (Apache-2.0), OTel Collector (Apache-2.0), ClickHouse (Apache-2.0). Como se consumen
  como contenedores separados (no se enlaza código), el riesgo de contaminación es bajo, pero
  **documentar** las licencias de las imágenes distribuidas.

---

*Fuente: reconocimiento de `pentagi-reference` (frontend/, observability/, backend/pkg/observability/,
docker-compose-*.yml, schema.graphqls). Solo lectura; no se copió código.*
