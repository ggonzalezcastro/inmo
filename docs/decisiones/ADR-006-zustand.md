# ADR-006: Zustand sobre Redux/Context

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

El frontend React requiere estado global para: autenticación (JWT token, usuario actual), conexión WebSocket (estado de conexión, eventos recibidos), y estado de leads/negocio. El problema era elegir entre Redux (estándar histórico), React Context + useReducer, o Zustand (alternativa moderna más ligera).

Redux Toolkit reduce boilerplate pero sigue siendo verboso. Context + useReducer funciona pero puede resultar en providers anidados y re-renders innecesarios. Zustand promete simplicidad sin perder funcionalidad.

## Decisión

Usar Zustand para todo el estado global del frontend. Los stores se organizan por feature:
- `store/auth.js`: Token JWT, usuario actual, login/logout
- `store/websocket.js`: Estado de conexión WebSocket, cola de eventos
- `store/leads.js`: Cache de leads, operaciones CRUD
- `store/pipeline.js`: Stages del pipeline, transiciones

Cada store es un archivo simple con:
- Slice de estado inicial
- Acciones (setters) definidas con `set`
- Selectores para derived data
- Middleware para persistencia (localStorage) donde aplique

Vite proxy configura `/api` y `/auth` hacia backend FastAPI.

## Consecuencias

**Pros:**
- API simple y concisa: mínimo boilerplate comparado con Redux
- No providers anidados: un solo `useStore` hook por fuera de componentes
- Re-renders optimizados automáticos: Zustand solo causa render en subscribers afectados
- TypeScript support bueno: tipos inferidos de estado y acciones
- DevTools disponibles para time-travel debugging
- Persistencia fácil con middleware `persist`
- Código más pequeño: archivos de ~50 líneas vs ~200 para Redux equivalent

**Contras:**
- Ecosistema menor: menos librerías third-party que Redux
- Menos convenciones establecidas: libertad puede llevar a inconsistencia entre desarrolladores
- Documentación menos extensa para casos edge
- Learning curve para equipos acostumbrados a Redux
- Posible sobre-uso: no todo estado necesita ser global (muchos casos locales con useState son suficientes)
