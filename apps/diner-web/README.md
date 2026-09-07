# Diner web

Frontend móvil para el acceso de comensales.

## Desarrollo local

Con la API existente en `http://localhost:8000`:

```bash
npm install
npm run dev
```

Ejemplo de entrada: `http://localhost:5173/join/<join_context_key>`. También se acepta `/?join_context_key=<join_context_key>` para enlaces QR. Vite envía las solicitudes `/api/*` a la API y elimina el prefijo `/api`; puede cambiarse el destino con `DINER_API_PROXY_TARGET`.

Para una entrega en otro origen, `VITE_API_BASE_URL` puede definir la URL pública de la API. No contiene secretos.

## Verificación

```bash
npm run typecheck
npm test
npm run build
```
