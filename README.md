# Growvia Datos

App aparte del CRM para **completar bases de empresas** antes de subirlas al CRM con *Cargar base*.

1. **Subir** un Excel con una columna RUC o Razón social / Cliente final. Las demás columnas se conservan.
2. **Buscar el RUC** en el padrón reducido de SUNAT. Es gratis; se descarga solo y se guarda una copia en Azure.
3. **Revisar los RUC dudosos**: probables, varios posibles, no encontrados o inválidos.
4. **Consultar SUNAT** con apiconsulta.dev. Por cada empresa se puede traer:
   - el representante legal y su DNI;
   - los teléfonos y correos;
   - los trabajadores en planilla.

   Cada dato es una consulta del plan. Antes de empezar, la app muestra cuántas se van a gastar. Lo ya consultado en los últimos 60 días se reutiliza sin pagar de nuevo.
5. **Revisar y completar**:
   - elegir el representante;
   - corregir el teléfono o el correo;
   - marcar el segmento (micro, pequeña, mediana o grande);
   - anotar las líneas por operador (Movistar, Claro, Entel y Bitel).
6. **Descargar** el Excel con la plantilla del CRM:
   - las 11 columnas de Ann;
   - columnas de control;
   - las columnas originales.

   Se puede filtrar por micro o pymes.

**Accesos**: se entra con un código que llega al correo. Solo entran los correos que un administrador agregó en *Accesos*. Los correos de `ADMIN_INICIAL` siempre son administradores.

Las líneas por RUC se revisan a mano en *Checa tus líneas* de OSIPTEL. En el CRM, la ficha de la empresa la abre en una ventana al costado.

## Estructura
- `backend/`: FastAPI y PostgreSQL. La app crea sus tablas sola al arrancar (`app/esquema.sql`).
- `frontend/`: React y Vite. En producción el backend sirve el frontend compilado.
- `Dockerfile`: una sola imagen (puerto 8000).

## Probar en tu computadora
```bash
# Base de datos local
createdb growvia_datos

# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env    # y ajusta DATABASE_URL
set -a; source ../.env; set +a
uvicorn tests.mock_apiconsulta:app --port 4010 &   # apiconsulta de mentira (no gasta)
uvicorn app.main:app --port 8010 --reload

# Frontend (en otra terminal)
cd frontend && npm install && npm run dev          # http://localhost:5174
```
Sin `SMTP_HOST`, el código para entrar aparece en la consola del backend.

Para probar sin descargar el padrón real (unos 400 MB), deja un zip de prueba en `/tmp/padron/padron_reducido_ruc.zip`. Debe tener el mismo formato: `RUC|NOMBRE|ESTADO|CONDICIÓN|UBIGEO|…`, separado por `|`, en latin-1.

Pruebas: `cd backend && python -m pytest -q`

## Variables (Azure)
| Variable | Qué es |
|---|---|
| `DATABASE_URL` | Secreto `db-url`. Base `growvia_datos` en `growviabd-eastus`, usuario `datos_app`, `sslmode=require` |
| `JWT_SECRETO` | Secreto `jwt-secreto`. Texto aleatorio largo |
| `ENTORNO` | `produccion` (ya viene en la imagen) |
| `ADMIN_INICIAL` | `jmedrano@corevia.global` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `CORREO_REMITENTE` | Los mismos del CRM |
| `SMTP_PASS` | Secreto `smtp-pass` (el mismo del CRM) |
| `APICONSULTA_TOKEN` | Secreto `apiconsulta-token` |
| `APICONSULTA_LIMITE_MES` | 100 con el plan gratis, 100000 con Plus |
| `AZURE_STORAGE_CONNECTION_STRING` | Secreto `storage-conn`. Cuenta `growviacrmarchivos`, contenedor `padron` |

Nunca escribas tokens ni contraseñas en el repositorio ni en el chat.

## Publicar en Azure (Cloud Shell)
Ver [`deploy/AZURE.md`](deploy/AZURE.md).
