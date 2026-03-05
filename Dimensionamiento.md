## Dimensionamiento

### Supuestos y carga estimada

| **Métrica** | **Valor** |
|---|---|
| Brokers | 10 |
| Leads totales | 3.5M |
| Agentes humanos concurrentes | 200 |
| WebSocket connections simultáneas | ~200–250 |
| Mensajes WhatsApp/día (estimado) | ~50k–100k (AI activa 20% del día) |
| LLM calls/día | ~30k–60k (con semantic cache reduciendo ~30%) |
| Celery tasks/día | ~10k–20k (scoring, campaigns, voice) |

### Región recomendada

- **Primaria**: AWS **São Paulo** (`sa-east-1`) por latencia hacia Chile.
- **Alternativa**: GCP **southamerica-east1**.

### Arquitectura propuesta (alto nivel)

```text
CloudFlare (CDN + WAF)
  │
ALB (Application Load Balancer)
  ├─ ECS Fargate (FastAPI) x2
  ├─ ECS Fargate (FastAPI) x2
  │
  └─ Dependencias
     ├─ RDS PostgreSQL (Multi-AZ + pgvector)
     ├─ ElastiCache Redis (idealmente cluster mode según necesidad)
     └─ ECS Fargate (Celery workers x3 + Celery beat x1)
```

### Sizing concreto (infra)

| **Servicio** | **Spec** | **Costo estimado (USD/mes)** |
|---|---|---:|
| ECS Fargate - API | 2 tasks × 2 vCPU / 4GB RAM | ~$120 |
| ECS Fargate - Celery workers | 3 tasks × 2 vCPU / 4GB RAM | ~$180 |
| ECS Fargate - Celery beat | 1 task × 0.5 vCPU / 1GB RAM | ~$20 |
| RDS PostgreSQL 16 | `db.r6g.xlarge` (4 vCPU, 32GB) Multi-AZ, 500GB gp3 | ~$550 |
| ElastiCache Redis | `r6g.large` (2 vCPU, 13GB), single node | ~$150 |
| ALB | Application Load Balancer + WebSocket support | ~$30 |
| CloudFront + S3 | Frontend estático | ~$10 |
| ECR | Container registry | ~$5 |
| CloudWatch | Logs + monitoring | ~$30 |
| Secrets Manager | API keys | ~$5 |
| **Total infra** |  | **~$1,100/mes** |

### Costos LLM / Voz (donde se va el gasto real)

| **Proveedor** | **Estimado/mes (30–60k calls)** |
|---|---:|
| Gemini (primario) | $300–800 (Flash es barato) |
| Claude (fallback) | $200–500 |
| OpenAI (fallback) | $200–500 |
| VAPI (voz) | Variable, ~`$0.05/min` |
| **Total LLM estimado** | **$500–$1,500/mes** |

**Total estimado (infra + LLMs)**: **~$1,600–$2,600/mes**

### Por qué ECS Fargate (y no EC2 / Kubernetes)

- **No EC2**: administrar servidores para esta escala (10 brokers) no justifica el overhead operativo.
- **No EKS (Kubernetes)**: overkill; agrega costo (ej. control plane) y complejidad.
- **Fargate**: pago por uso, auto-scaling simple, zero server management; buen fit para esta etapa.

### Puntos críticos a resolver antes de producción

#### 1) PostgreSQL con 3.5M leads + pgvector

Índices mínimos (ejemplo):

```sql
CREATE INDEX IF NOT EXISTS idx_leads_broker_id ON leads(broker_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_lead_id ON chat_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding
  ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

#### 2) WebSocket a escala (200 agentes)

`ws_manager` es **in-memory**. Con 2+ instancias API necesitas **Redis pub/sub** para broadcast entre instancias.

```text
Instancia-1 publica evento → Redis pub/sub → Instancia-2 lo re-broadcast a sockets conectados ahí
```

#### 3) Celery: colas por prioridad

```python
CELERY_TASK_ROUTES = {
    "app.tasks.chat_tasks.*": {"queue": "chat_high"},          # alta prioridad
    "app.tasks.campaign_executor.*": {"queue": "campaigns"},   # puede esperar
    "app.tasks.scoring_tasks.*": {"queue": "scoring"},         # background
}
```

#### 4) Rate limiting por broker (presupuesto LLM)

Implementar rate limiting Redis por `broker_id` para que un broker no consuma todo el budget.

### Alternativa más barata (Railway / Render) para validar

Si quieres lanzar rápido y crecer después:

| **Servicio** | **Costo** |
|---|---:|
| Railway (API + Workers) | ~$50–100/mes |
| Supabase PostgreSQL (Pro) | $25/mes |
| Upstash Redis | $10/mes |
| Vercel (frontend) | $0–20/mes |
| **Total** | **~$100–150/mes + LLMs** |

**Trade-off**: con **3.5M leads**, Supabase se queda corto y el scaling de WebSockets va a doler.

### Recomendación por fases

- **Fase 1 (0–3 brokers, validación)**: Railway/Render, **~$150/mes + LLMs**. Rápido para iterar.
- **Fase 2 (3–10 brokers, producción real)**: AWS ECS Fargate en `sa-east-1`, **~$1,100/mes + LLMs**.

### Acción inmediata más importante

- Resolver **WebSocket multi-instancia** con Redis pub/sub.
- Verificar **connection pooling** en PostgreSQL (SQLAlchemy): ajustar `pool_size` y `max_overflow` para ~200 agentes concurrentes.

### Próximos pasos

Si quieres, puedo:
- Armar **Dockerfiles + ECS task definitions** (API, workers, beat).
- Proponer el diseño de **Redis pub/sub** para WebSocket (y cambios mínimos en `ws_manager`).