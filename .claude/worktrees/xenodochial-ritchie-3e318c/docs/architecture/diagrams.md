---
title: Diagramas de Arquitectura
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# Diagramas de Arquitectura

## 1. Diagrama de Arquitectura del Sistema

```mermaid
flowchart TB
    subgraph clients [Clientes]
        BROWSER[Navegador Web]
        TGBOT[Telegram Bot]
        WABOT[WhatsApp]
        PHONE[Teléfono]
    end

    subgraph frontend [Frontend - React + Vite]
        SPA[Single Page App]
        ZUSTAND[Zustand Stores]
    end

    subgraph backend [Backend - FastAPI]
        ROUTES[Routes Layer]
        AUTH[Auth Middleware]
        RATE[Rate Limiter]
        subgraph services [Service Layer]
            CHAT_SVC[Chat Service]
            VOICE_SVC[Voice Service]
            LEAD_SVC[Lead Service]
            PIPE_SVC[Pipeline Service]
            CAMP_SVC[Campaign Service]
            APT_SVC[Appointment Service]
            BROKER_SVC[Broker Service]
        end
        subgraph providers [Provider Layer]
            LLM_PROV[LLM Providers]
            VOICE_PROV[Voice Providers]
            CHAT_PROV[Chat Providers]
        end
    end

    subgraph workers [Background Workers]
        CELERY[Celery Worker]
        BEAT[Celery Beat]
    end

    subgraph infra [Infraestructura]
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        GCAL[Google Calendar]
    end

    subgraph external [APIs Externas]
        GEMINI[Google Gemini]
        CLAUDE[Anthropic Claude]
        OPENAI_API[OpenAI GPT]
        VAPI[VAPI.ai]
        BLAND[Bland AI]
        TGAPI[Telegram API]
    end

    BROWSER --> SPA
    SPA --> ZUSTAND
    SPA --> ROUTES
    TGBOT --> ROUTES
    WABOT --> ROUTES
    PHONE --> VAPI
    PHONE --> BLAND

    ROUTES --> AUTH
    AUTH --> RATE
    RATE --> services

    CHAT_SVC --> CHAT_PROV
    VOICE_SVC --> VOICE_PROV
    services --> LLM_PROV

    LLM_PROV --> GEMINI
    LLM_PROV --> CLAUDE
    LLM_PROV --> OPENAI_API
    VOICE_PROV --> VAPI
    VOICE_PROV --> BLAND
    CHAT_PROV --> TGAPI

    services --> PG
    services --> REDIS
    APT_SVC --> GCAL

    CELERY --> PG
    CELERY --> REDIS
    BEAT --> CELERY
```

## 2. Diagrama de Base de Datos (ERD)

```mermaid
erDiagram
    BROKERS {
        int id PK
        string name
        string slug UK
        string phone
        string email
        boolean is_active
        datetime created_at
    }

    USERS {
        int id PK
        string email UK
        string hashed_password
        string name
        enum role
        int broker_id FK
        boolean is_active
    }

    LEADS {
        int id PK
        string phone
        string name
        string email
        string status
        float lead_score
        json lead_metadata
        string pipeline_stage
        int assigned_to FK
        int broker_id FK
    }

    BROKER_PROMPT_CONFIGS {
        int id PK
        int broker_id FK
        string agent_name
        text identity_prompt
        text business_context
        boolean enable_appointment_booking
    }

    BROKER_LEAD_CONFIGS {
        int id PK
        int broker_id FK
        json field_weights
        int cold_max_score
        int warm_max_score
        int hot_min_score
    }

    BROKER_VOICE_CONFIGS {
        int id PK
        int broker_id FK
        string provider
        json provider_credentials
        string phone_number_id
        string assistant_id_default
    }

    BROKER_CHAT_CONFIGS {
        int id PK
        int broker_id FK
        json enabled_providers
        enum default_provider
    }

    APPOINTMENTS {
        int id PK
        int lead_id FK
        int agent_id FK
        enum appointment_type
        enum status
        datetime start_time
        datetime end_time
        string meet_url
    }

    CAMPAIGNS {
        int id PK
        string name
        enum channel
        enum status
        enum triggered_by
        int broker_id FK
    }

    CAMPAIGN_STEPS {
        int id PK
        int campaign_id FK
        int step_number
        enum action
        int message_template_id FK
        int delay_hours
    }

    CAMPAIGN_LOGS {
        int id PK
        int campaign_id FK
        int lead_id FK
        int step_number
        enum status
    }

    MESSAGE_TEMPLATES {
        int id PK
        string name
        enum channel
        text content
        enum agent_type
        json variables
        int broker_id FK
    }

    VOICE_CALLS {
        int id PK
        int lead_id FK
        int campaign_id FK
        string phone_number
        string external_call_id UK
        enum status
        int duration
        text transcript
        text summary
        int broker_id FK
    }

    CALL_TRANSCRIPTS {
        int id PK
        int voice_call_id FK
        enum speaker
        text text_content
        float timestamp_sec
    }

    CHAT_MESSAGES {
        int id PK
        int lead_id FK
        int broker_id FK
        enum provider
        string channel_user_id
        text message_text
        enum direction
    }

    TELEGRAM_MESSAGES {
        int id PK
        int lead_id FK
        int telegram_user_id
        text message_text
        enum direction
    }

    ACTIVITY_LOG {
        int id PK
        int lead_id FK
        string action_type
        json details
        datetime ts
    }

    AUDIT_LOGS {
        int id PK
        int user_id FK
        string action
        string resource_type
        int resource_id
    }

    BROKERS ||--o{ USERS : "has"
    BROKERS ||--o| BROKER_PROMPT_CONFIGS : "has"
    BROKERS ||--o| BROKER_LEAD_CONFIGS : "has"
    BROKERS ||--o| BROKER_VOICE_CONFIGS : "has"
    BROKERS ||--o| BROKER_CHAT_CONFIGS : "has"
    BROKERS ||--o{ LEADS : "owns"
    BROKERS ||--o{ CHAT_MESSAGES : "owns"
    USERS ||--o{ APPOINTMENTS : "manages"
    USERS ||--o{ CAMPAIGNS : "creates"
    USERS ||--o{ VOICE_CALLS : "initiates"
    USERS ||--o{ AUDIT_LOGS : "generates"
    LEADS ||--o{ APPOINTMENTS : "has"
    LEADS ||--o{ VOICE_CALLS : "receives"
    LEADS ||--o{ CHAT_MESSAGES : "exchanges"
    LEADS ||--o{ TELEGRAM_MESSAGES : "exchanges"
    LEADS ||--o{ ACTIVITY_LOG : "generates"
    LEADS ||--o{ CAMPAIGN_LOGS : "targeted_by"
    CAMPAIGNS ||--o{ CAMPAIGN_STEPS : "contains"
    CAMPAIGNS ||--o{ CAMPAIGN_LOGS : "generates"
    CAMPAIGN_STEPS }o--o| MESSAGE_TEMPLATES : "uses"
    VOICE_CALLS ||--o{ CALL_TRANSCRIPTS : "has"
```

## 3. Diagrama de Flujo de Datos

### Flujo de Mensaje de Chat

```mermaid
flowchart TD
    A[Mensaje Entrante] --> B{Webhook}
    B -->|Telegram| C[ChatOrchestratorService]
    B -->|WhatsApp| C
    C --> D[Resolver/Crear Lead]
    D --> E[LeadContextService]
    E -->|Cache Hit| F[Contexto del Lead]
    E -->|Cache Miss| G[(PostgreSQL)]
    G --> F
    F --> H[LLM Analysis]
    H --> I{Datos Extraídos?}
    I -->|Sí| J[Actualizar Lead Metadata]
    I -->|No| K[Scoring Service]
    J --> K
    K --> L[Calcular Score]
    L --> M[Pipeline Service]
    M --> N{Auto-avance?}
    N -->|Sí| O[Mover Etapa]
    N -->|No| P[LLM Generate Response]
    O --> P
    P --> Q[Enviar Respuesta]
    Q --> R[Persistir Mensaje]
    R --> S[Log Actividad]
```

### Flujo de Llamada de Voz

```mermaid
flowchart TD
    A[POST /calls/initiate] --> B[VoiceCallService]
    B --> C[Crear VoiceCall Record]
    C --> D[Voice Provider Factory]
    D --> E{Proveedor}
    E -->|VAPI| F[VapiProvider.make_call]
    E -->|Bland| G[BlandProvider.make_call]
    F --> H[external_call_id]
    G --> H
    H --> I[Actualizar VoiceCall]
    I --> J[Webhook llega]
    J --> K[handle_webhook]
    K --> L[WebhookEvent normalizado]
    L --> M{Tipo de Evento}
    M -->|CALL_ENDED| N[Generar Transcript]
    M -->|TRANSCRIPT| O[Log Parcial]
    M -->|STATUS| P[Actualizar Estado]
    N --> Q[Celery Task]
    Q --> R[CallAgentService]
    R --> S[LLM Summary]
    S --> T[Actualizar Lead Score]
```

## 4. Diagrama de Componentes

```mermaid
flowchart TB
    subgraph routes [Routes - API Layer]
        R_AUTH[auth.py]
        R_LEADS[leads.py]
        R_CHAT[chat.py]
        R_VOICE[voice.py]
        R_PIPE[pipeline.py]
        R_CAMP[campaigns.py]
        R_APT[appointments.py]
        R_BROKER[broker_config.py]
        R_TMPL[templates.py]
        R_WH[webhooks.py]
    end

    subgraph svc [Services - Business Logic]
        subgraph svc_voice [voice/]
            V_BASE[BaseVoiceProvider]
            V_FACTORY[factory.py]
            V_CALL[call_service.py]
            V_AGENT[call_agent.py]
            V_VAPI[providers/vapi/]
            V_BLAND[providers/bland/]
        end
        subgraph svc_llm [llm/]
            L_BASE[BaseLLMProvider]
            L_FACTORY[factory.py]
            L_FACADE[facade.py]
            L_GEMINI[gemini_provider.py]
            L_CLAUDE[claude_provider.py]
            L_OPENAI[openai_provider.py]
        end
        subgraph svc_chat [chat/]
            C_BASE[BaseChatProvider]
            C_ORCH[orchestrator.py]
            C_SVC[service.py]
            C_TG[telegram_provider.py]
            C_WA[whatsapp_provider.py]
        end
        subgraph svc_broker [broker/]
            B_CONFIG[config_service.py]
            B_INIT[init_service.py]
            B_VOICE[voice_config_service.py]
            B_PROMPT[prompt_service.py]
        end
        subgraph svc_leads [leads/]
            LD_SVC[lead_service.py]
            LD_CTX[context_service.py]
            LD_SCORE[scoring_service.py]
        end
        subgraph svc_pipe [pipeline/]
            P_ADV[advancement_service.py]
            P_MET[metrics_service.py]
        end
    end

    subgraph tasks [Background Tasks]
        T_CAMP[campaign_executor]
        T_VOICE[voice_tasks]
        T_SCORE[scoring_tasks]
        T_TG[telegram_tasks]
    end

    subgraph models [Data Models]
        M_USER[User]
        M_BROKER[Broker]
        M_LEAD[Lead]
        M_APT[Appointment]
        M_CAMP[Campaign]
        M_VOICE[VoiceCall]
        M_CHAT[ChatMessage]
    end

    R_VOICE --> V_CALL
    R_VOICE --> V_FACTORY
    R_CHAT --> C_ORCH
    R_LEADS --> LD_SVC
    R_PIPE --> P_ADV
    R_CAMP --> T_CAMP

    V_CALL --> V_FACTORY
    V_FACTORY --> V_VAPI
    V_FACTORY --> V_BLAND
    V_AGENT --> L_FACADE

    C_ORCH --> LD_SVC
    C_ORCH --> LD_CTX
    C_ORCH --> L_FACADE
    C_ORCH --> LD_SCORE
    C_ORCH --> P_ADV

    svc --> models
```
