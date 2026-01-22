# Plan de Implementación: Sistema de Brokers con Configuración

## Resumen
Este es un sistema grande que requiere implementación completa de modelos, migraciones, servicios y endpoints. Voy a implementarlo de forma estructurada.

## Fases de Implementación

### ✅ Fase 1: Modelos Creados
- [x] broker.py con Broker, BrokerPromptConfig, BrokerLeadConfig
- [x] Actualizado user.py con UserRole enum y broker_id

### 🔄 Fase 2: Migración (En Progreso)
- [ ] Crear tablas: brokers, broker_prompt_configs, broker_lead_configs
- [ ] Crear enum UserRole si no existe
- [ ] Migrar datos existentes de users
- [ ] Actualizar tabla users (agregar broker_id, cambiar broker_name a name)

### ⏳ Fase 3: Servicios
- [ ] Crear BrokerConfigService
- [ ] Crear middleware Permissions
- [ ] Modificar LeadContextService para usar prompts de BD
- [ ] Modificar ScoringService para usar config de BD

### ⏳ Fase 4: Endpoints
- [ ] routes/broker_config.py
- [ ] routes/broker_users.py
- [ ] Actualizar auth para incluir role y broker_id en JWT

### ⏳ Fase 5: Integración
- [ ] Filtrar leads por broker_id
- [ ] Filtrar por agent_id si es agente
- [ ] Actualizar todas las queries existentes

## Nota
Debido a la complejidad del sistema, la implementación completa requiere múltiples pasos. ¿Quieres que continúe con todas las fases o prefieres que lo haga por partes?


