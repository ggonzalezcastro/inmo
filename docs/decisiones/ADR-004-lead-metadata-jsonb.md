# ADR-004: lead_metadata JSONB para estado conversacional

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

Los leads de real estate tienen una gran variedad de atributos que varían según el contexto: presupuesto exacto, zonas de interés, tipo de propiedad preferida, estado emocional, último mensaje, historial de interacciones, puntuación de scoring, y muchos más. El schema rigid tradicional de SQL no puede acomodar esta variedad sin multiplicar el número de columnas o tablas.

Además, el estado conversacional de la AI (último tema discutido, información ya confirmada, flags de seguimiento) necesita almacenarse de forma flexible sin constantes migraciones de schema.

## Decisión

Usar columna `lead_metadata` de tipo JSONB en la tabla `leads` para almacenar:
- Datos dinámicos del lead: presupuesto, ubicaciones, tipos de propiedad, timeline
- Estado conversacional: último topic, información confirmada, flags de seguimiento
- Datos de scoring: componentes de puntaje, razones de calificación
- Metadatos varios: fuente del lead, preferencias de contacto, sentiment

La columna está encriptada a nivel de aplicación (ver `app/core/encryption.py`) para proteger PII.

Acceso a campos específicos mediante:
- PostgreSQL JSONB operators para queries eficientes (`->`, `->>`, `@>`)
- Helpers en `LeadContext` que extraen tipos seguros del JSONB

## Consecuencias

**Pros:**
- Flexibilidad de schema: nuevos campos agregados sin migraciones
- Desenvolvimento rápido: no hay que planear schema para features futuras
- Datos relacionados juntos: todo el contexto de un lead en un lugar
- Índices JSONB disponibles para queries eficientes sobre campos anidados
- Encriptación a nivel de aplicación protege PII sensible
- Reducción de tablas: no hay necesidad de tablas de metadatos separadas

**Contras:**
- Sin type safety en nivel de base de datos: datos pueden tener estructura inesperada
- Queries complejas para campos dentro del JSONB (aunque JSONB operators ayudan)
- Validación de schema transferida a la aplicación (no hay constraint de DB)
- Documentación de estructura más difícil: no hay schema formal visible en DB
- Posibles problemas de performance con JSONB muy grandes (fragmentación)
- Debugging harder: datos en JSONB menos visibles que columnas dedicadas
