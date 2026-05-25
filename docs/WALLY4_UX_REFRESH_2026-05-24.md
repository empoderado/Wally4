# UX refresh Wally4 - 2026-05-24

## Alcance

Se mejoro la capa visual de Wally4 sin cambiar consultas, vistas, reglas ni logica funcional de reportes.

## Cambios aplicados

- Nuevo shell visual global en `app.py`.
- Sidebar mas legible, con bloque de estado de base, puerto y modo.
- Encabezados de pagina consistentes desde `services.ui.page_title`.
- Boton comun `Actualizar` en cada modulo.
- KPIs redisenados con cards blancas, sombra discreta y acento por estado.
- Secciones con jerarquia visual mas clara.
- Tablas con borde, radio consistente y mejor separacion visual.
- Botones de descarga/accion con estilo uniforme.
- Correccion de texto `Codigo` en pies tecnicos.
- Escape HTML en componentes comunes para evitar que valores de texto rompan el layout.

## Funcionalidad preservada

- Las consultas siguen usando `WallyBD`.
- Los reportes siguen usando las mismas vistas autorizadas.
- El bloqueo runtime a `StudioF` sigue activo.
- No se alteraron scripts de refresco Mirror ni reglas de auditoria.

## Validacion

```text
compileall app.py services modules agents scripts: OK
scripts/ux_smoke_queries.py: OK
http://127.0.0.1:8504: HTTP 200 OK
```

Smoke UX:

| Modulo | Estado |
| --- | --- |
| Resumen Ventas | OK |
| Gerencia | OK |
| Existencias | OK |
| Embarques y Coleccion | OK |
| CRM | OK |
| Traslados | OK |
| Auditoria | OK |
| Presupuesto | OK |
| Reportes | OK |

## Pendiente visual

- Revisión manual en navegador por tamaños de pantalla.
- Si se desea, crear mockup en Figma con el complemento de Figma y usarlo como referencia para una segunda iteracion.
