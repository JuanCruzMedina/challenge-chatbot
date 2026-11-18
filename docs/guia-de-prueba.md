# Guía de prueba del asistente

Todos los datos de esta guía son **inventados** (una empresa ficticia, "Demo Studio"). Sirve para probar el asistente en el chat web o en la terminal y comparar lo que responde con lo que debería responder.

## 1. Cómo levantarlo

```
cd challenge-chatbot
uv run python scripts/seed_workspace.py          # deja el workspace limpio (var/workspace)
uv run langgraph dev --no-browser                # servidor en http://localhost:2024
```

Chat web: `https://agentchat.vercel.app/?apiUrl=http://localhost:2024&assistantId=agent` (hilo nuevo con el lápiz).
Chat de terminal: `uv run python -m ecosystem_assistant.chat`.
Con Claude: `LLM_PROVIDER=anthropic` en `.env` (tope de gasto en `ANTHROPIC_MAX_USD`, por defecto 1 USD).

Si probás escrituras y querés volver al estado inicial, corré de nuevo el `seed_workspace.py`.

## 2. Los datos inventados

**Empresa:** Demo Studio. **Clientes:** Demo Grocery y Demo Logistics.

| Aplicación | Cliente | Servicios |
|---|---|---|
| Storefront | Demo Grocery | catalog, orders, payments, notifications |
| Driver App | Demo Logistics | driver |
| Fleet Tracker | Demo Logistics | tracking, routing |

| Servicio | Equipo | Tech lead | Provee API | Consume API | Publica eventos | Se suscribe a |
|---|---|---|---|---|---|---|
| catalog-service | catalog-team | Nora Beltrán | catalog-api | — | product.price_changed | — |
| orders-service | orders-team | Tomás Aguirre | orders-api | catalog-api, payments-api | order.created, order.cancelled | payment.confirmed, payment.failed, product.price_changed |
| payments-service | payments-team | Valeria Sosa | payments-api (v1) | — | payment.confirmed, payment.failed | order.created |
| notifications-service | communications-team | Iván Prado | — | — | — | order.created, order.cancelled, payment.failed |
| driver-service | driver-team | Diego Núñez | — | tracking-api | — | route.assigned |
| tracking-service | tracking-team | Bruno Salas | tracking-api | — | vehicle.position_updated | — |
| routing-service | routing-team | Elena Pardo | — | — | route.assigned | vehicle.position_updated |

**Product Owners de producto:** Sofía Mendoza (Demo Grocery) y Camila Ortega (Demo Logistics).

**Documentos con respuestas concretas:**
- `payments-service/docs/api-v1.md`: payments-api v1 no soporta reintentos automáticos; el resultado del cobro es asíncrono (`payment.confirmed` o `payment.failed`). Está marcada como **deprecada**, con fin de vida el 2027-03-31, y la consume orders-service.
- `catalog-service/docs/api.md`: límite de 200 solicitudes por minuto por consumidor. `tracking-service/docs/api.md`: 300 por minuto.
- Runbooks: precios desactualizados (catalog), orden trabada en PAYMENT_PENDING (orders), cobros fallidos (payments), correos demorados (notifications), vehículo que desaparece del mapa (tracking).
- ADR-001 de orders-service: arquitectura orientada a eventos.

## 3. Frases para pegar y respuestas sugeridas

Cada frase va en su propio bloque para copiarla entera. La "respuesta sugerida" dice qué contenido debería tener lo que responde el asistente: la redacción cambia de una corrida a otra, lo que importa son los datos y la herramienta usada. Probá cada grupo en un hilo nuevo.

### Leer y buscar

**1.**

```text
Listame todos los equipos y quién lidera cada uno.
```

**Respuesta sugerida:** los 7 equipos con su tech lead: catalog-team (Nora Beltrán), communications-team (Iván Prado), driver-team (Diego Núñez), orders-team (Tomás Aguirre), payments-team (Valeria Sosa), routing-team (Elena Pardo) y tracking-team (Bruno Salas). Puede aclarar que el grafo da el lead de cada servicio y no un "líder de equipo".

**2.**

```text
¿Quién es dueño del servicio de tracking y quién lo lidera?
```

**Respuesta sugerida:** tracking-team es dueño de tracking-service y lo lidera Bruno Salas, con citas `[K1]` y/o `[D1]`.

**3.**

```text
¿Quién consume la API de pagos y qué versiones están deprecadas?
```

**Respuesta sugerida:** orders-service consume payments-api; la v1 está deprecada, con fin de vida el 2027-03-31 y orders-service como consumidor afectado.

**4.**

```text
Un cliente ve un precio desactualizado, ¿qué hago?
```

**Respuesta sugerida:** los pasos del runbook de precios: consultar `GET /products/{id}` en catalog-service, verificar si se publicó `product.price_changed`, y si orders-service muestra otro valor, invalidar su caché y avisar a orders-team; si falló la carga, reintentar desde el panel comercial. Escalamiento: catalog-team.

**5.**

```text
¿Cuántas solicitudes por minuto puede hacer un consumidor a la API de catálogo?
```

**Respuesta sugerida:** 200 por minuto por consumidor; si se pasa, devuelve `429`.

**6.**

```text
¿Qué aplicaciones tiene Demo Logistics y qué servicios tiene cada una?
```

**Respuesta sugerida:** Driver App (driver-service) y Fleet Tracker (routing-service y tracking-service).

**7.**

```text
¿Quién es el Product Owner de Demo Grocery?
```

**Respuesta sugerida:** Sofía Mendoza (figura en la visión del cliente y en las épicas del catálogo).

### Escribir y vincular

**8.**

```text
Creá el documento docs/consumo-pagos.md en orders-service explicando que orders-service consume la API de pagos para cobrar cada orden.
```

**Respuesta sugerida:** crea el documento sin pedir confirmación, con `about: ["payments-api"]` en el front matter, y dice qué vínculos puso y si dejó algún nombre afuera. Verificalo con `cat var/workspace/repos/orders-service/docs/consumo-pagos.md`.

**9.**

```text
¿Qué documentos hablan de payments-api?
```

**Respuesta sugerida:** lista `orders-service/docs/consumo-pagos.md` como documento vinculado directamente a la API (usa la consulta `documents_about`). Puede mencionar además otros documentos que la nombran en su texto, aclarando que no están vinculados en el grafo.

**10.**

```text
Agregá al README de driver-service que Gaspar Noriega es el Product Owner de driver-team.
```

**Respuesta sugerida:** agrega la línea al final de `README.md` de driver-service, sin repreguntar, y dice que el cambio se podrá buscar después de la próxima ingesta. Si la corriste antes, la línea puede aparecer repetida.

### Editar (piden confirmación)

**11.**

```text
En payments-service, en docs/api-v1.md, cambiá la regla de reintentos: ahora v1 reintenta hasta 3 veces.
```

**Respuesta sugerida:** primero busca la regla actual ("v1 does not support automatic retries…") y muestra un diff con el cambio, preguntando si lo aplica. No escribe todavía.

Contestá:

```text
Sí, aplicalo.
```

**Respuesta sugerida:** confirma que reemplazó la regla; en `api-v1.md` ahora dice que v1 reintenta hasta 3 veces.

**12.**

```text
Marcá como obsoleto docs/api-v1.md de payments-service, reemplazado por docs/api-v2.md.
```

**Respuesta sugerida:** muestra el front matter que agregaría (`status: obsolete`, `obsolete_reason`, `replaced_by: docs/api-v2.md`) y espera tu respuesta.

Contestá:

```text
Sí.
```

**Respuesta sugerida:** confirma que marcó el documento como obsoleto; el cuerpo no cambia.

**13.**

```text
Cambiá los vínculos de docs/consumo-pagos.md en orders-service: ahora también habla de payments-service.
```

**Respuesta sugerida:** deja `about` con `payments-api` y `payments-service`, e informa la lista anterior (`payments-api`). No pide confirmación, porque solo toca el front matter. Requiere haber hecho la frase 8 antes.

### Conflictos y límites

**14.**

```text
El líder de orders-team es Juan Pérez.
```

**Respuesta sugerida:** dice que la documentación indica a Tomás Aguirre como tech lead de orders-service y pregunta cuál es el dato correcto. No modifica nada.

Contestá:

```text
Dejá el actual, no cambies nada.
```

**Respuesta sugerida:** confirma que no modifica nada y que se mantiene Tomás Aguirre.

**15.**

```text
Borrá el servicio orders-service completo.
```

**Respuesta sugerida:** dice que no puede borrar servicios ni archivos (solo lee, crea, agrega, edita, marca como obsoleto y vincula) y ofrece marcar como obsoletos sus documentos o agregar una nota de retiro. No llama a ninguna herramienta de escritura.

**16.**

```text
Hola, ¿cómo andás?
```

**Respuesta sugerida:** un saludo breve y qué puede hacer. No llama a ninguna herramienta.

### Mixto

**17.**

```text
Fijate quién lidera tracking-service y anotalo en un documento docs/lider.md de ese servicio.
```

**Respuesta sugerida:** consulta primero (Bruno Salas, tech lead de tracking-team) y después crea `docs/lider.md`, avisando con qué `about` lo vinculó.

## 4. Revisión de documentación de un PR

Se corre en la terminal, no en el chat. El PR es inventado (`data/ecosystem/prs/pr-101-payments-api-v2/pr.yaml`: payments-api v2 con reintentos automáticos y v1 deprecada). `--dry-run` trabaja sobre una copia y no cambia nada real; cada corrida cuesta centavos.

```bash
cd challenge-chatbot
LLM_PROVIDER=anthropic uv run python -m ecosystem_assistant.pr_review data/ecosystem/prs/pr-101-payments-api-v2/pr.yaml --dry-run
```

**Respuesta sugerida:** propone actualizar la documentación de payments-service (la regla de reintentos de `docs/api-v1.md` o un documento de la v2) y muestra el diff, con la línea `dry run: nothing was written for real`. Puede variar entre corridas.

Para ver el caso en que **no** hay que cambiar nada, copiá ese archivo, cambiá `description` por `Renombra funciones internas, sin cambios de comportamiento.` y volvé a correrlo:

```bash
cp data/ecosystem/prs/pr-101-payments-api-v2/pr.yaml /tmp/pr-refactor.yaml
# editá /tmp/pr-refactor.yaml: id PR-102, título y descripción de refactor, sin cambios en docs
LLM_PROVIDER=anthropic uv run python -m ecosystem_assistant.pr_review /tmp/pr-refactor.yaml --dry-run
```

**Respuesta sugerida:** `no documentation change`, con una explicación breve de por qué no hace falta tocar la documentación.

## 5. Qué mirar con ojo crítico

- Las respuestas citan evidencia (`[K1]` del grafo, `[D2]` de documentos). "Cita evidencia existente" no garantiza que sea cierto.
- Ante una pregunta con una frase distinta, el resultado puede cambiar: el modelo no es determinista. Una misma pregunta puede fallar alguna vez (por ejemplo la revisión del PR de reintentos acierta cerca de 4 de cada 5 veces).
- Los documentos nuevos tardan hasta la siguiente pregunta en ser buscables; el grafo los ve por sus vínculos `about`.
- Un documento nuevo puede quedar sin vincular si el modelo olvida el nombre; en ese caso corregilo con la frase 13.
- Medido con Claude Haiku 5.5: ruteo 20/20 y revisión de PRs 5/6 o 6/6 según la corrida (muestras chicas, un solo modelo). Con el modelo local (Ollama) no se midió.
