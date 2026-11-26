# Publicar Growvia Datos en Azure

- **Dónde:** Container App `growvia-datos` en el grupo `growvia-crm-rg`, dentro del mismo entorno del CRM (`growvia-crm-env`).
- **Escala:** mínimo 0 réplicas, así que solo cuesta cuando se usa.
- **Máximo 1 réplica:** los procesos en segundo plano van en una sola instancia.

Cada bloque se ejecuta en **Cloud Shell (Bash)**. Las contraseñas y tokens se guardan en variables y no se muestran en pantalla.

## 0. Preparar la sesión
```bash
az account set --subscription 3c583f4d-e7f0-47d5-82c6-ff6d6e1dc2ae
gh auth login            # si pide, código en https://github.com/login/device
cd ~ && rm -rf ~/growvia-datos && gh repo clone JhersonMB428/growvia-datos ~/growvia-datos && cd ~/growvia-datos && git log --oneline -1
```

## 1. Base de datos (solo la primera vez)
Crea el usuario `datos_app` y la base `growvia_datos` en el mismo servidor del CRM.

`psql` pide la contraseña de `admingrowvia`. Escríbela: no se ve mientras la escribes.
```bash
DB_PASS=$(openssl rand -hex 24)
psql "host=growviabd-eastus.postgres.database.azure.com port=5432 dbname=postgres user=admingrowvia sslmode=require" <<SQL
CREATE ROLE datos_app LOGIN PASSWORD '$DB_PASS';
GRANT datos_app TO admingrowvia;
CREATE DATABASE growvia_datos OWNER datos_app;
\\c growvia_datos
ALTER SCHEMA public OWNER TO datos_app;
GRANT ALL ON SCHEMA public TO datos_app;
SQL
DB_URL="postgresql://datos_app:${DB_PASS}@growviabd-eastus.postgres.database.azure.com:5432/growvia_datos?sslmode=require"
```
Las tablas se crean solas cuando la app arranca. Si al arrancar sale `permission denied for schema public`, falta el `ALTER SCHEMA` de arriba (en Azure la base nueva deja el esquema `public` a nombre del admin).

## 2. Juntar los secretos (sin mostrarlos)
```bash
CRM="-g growvia-crm-rg -n growvia-crm"
JWT=$(openssl rand -hex 32)
SMTP_PASS=$(az containerapp secret show $CRM --secret-name smtp-pass --query value -o tsv)
STORAGE=$(az storage account show-connection-string -g growvia-crm-rg -n growviacrmarchivos -o tsv)
ACR_PASS=$(az acr credential show -n growviaregistry --query "passwords[0].value" -o tsv)
env_crm() { az containerapp show $CRM --query "properties.template.containers[0].env[?name=='$1'].value | [0]" -o tsv; }
SMTP_HOST=$(env_crm SMTP_HOST); SMTP_PORT=$(env_crm SMTP_PORT); SMTP_USER=$(env_crm SMTP_USER)
REMITENTE=$(env_crm CORREO_REMITENTE | sed 's/Growvia CRM/Growvia Datos/')
echo "SMTP: $SMTP_HOST:$SMTP_PORT ($SMTP_USER) · remitente: $REMITENTE"
```
Ahora el token de apiconsulta. Si el CRM todavía lo tiene guardado, se copia de ahí:
```bash
API_TOKEN=$(az containerapp secret show $CRM --secret-name apiconsulta-token --query value -o tsv 2>/dev/null)
[ -z "$API_TOKEN" ] && echo "No está en el CRM: escríbelo con  read -s API_TOKEN" || echo "Token copiado del CRM"
```
Si dice que no está, ejecuta `read -s API_TOKEN` **solo en una línea**, pega el token y presiona Enter.

## 3. Construir la imagen
```bash
TAG=$(date +%Y%m%d%H%M)
az acr build -r growviaregistry -t growvia-datos:$TAG .
az acr repository show-tags -n growviaregistry --repository growvia-datos -o tsv | grep $TAG
```

## 4. Crear la Container App (solo la primera vez)
```bash
az containerapp create -g growvia-crm-rg -n growvia-datos --environment growvia-crm-env \
  --image growviaregistry.azurecr.io/growvia-datos:$TAG \
  --registry-server growviaregistry.azurecr.io --registry-username growviaregistry --registry-password "$ACR_PASS" \
  --ingress external --target-port 8000 --min-replicas 0 --max-replicas 1 --cpu 1 --memory 2Gi \
  --secrets db-url="$DB_URL" jwt-secreto="$JWT" smtp-pass="$SMTP_PASS" apiconsulta-token="$API_TOKEN" storage-conn="$STORAGE" \
  --env-vars DATABASE_URL=secretref:db-url JWT_SECRETO=secretref:jwt-secreto SMTP_PASS=secretref:smtp-pass \
    APICONSULTA_TOKEN=secretref:apiconsulta-token AZURE_STORAGE_CONNECTION_STRING=secretref:storage-conn \
    SMTP_HOST="$SMTP_HOST" SMTP_PORT="$SMTP_PORT" SMTP_USER="$SMTP_USER" CORREO_REMITENTE="$REMITENTE" \
    ADMIN_INICIAL=jmedrano@corevia.global APICONSULTA_LIMITE_MES=100 \
  --query properties.configuration.ingress.fqdn -o tsv
unset DB_PASS DB_URL JWT SMTP_PASS STORAGE ACR_PASS API_TOKEN
```
El último comando muestra la dirección de Azure (`growvia-datos.….azurecontainerapps.io`). Pruébala:
```bash
curl -s https://$(az containerapp show -g growvia-crm-rg -n growvia-datos --query properties.configuration.ingress.fqdn -o tsv)/api/salud
```
Debe responder `{"ok":true}`. La primera vez tarda entre 30 y 60 segundos porque la app arranca desde cero.

## 5. Dominio datos.growvia.global
1. Abre el **Zone Editor** del cPanel de growvia.global y crea dos registros:
   - **CNAME** `datos` → la dirección de Azure del paso 4.
   - **TXT** `asuid.datos` → el valor que devuelve este comando:
     ```bash
     az containerapp show -g growvia-crm-rg -n growvia-datos --query properties.customDomainVerificationId -o tsv
     ```
2. Espera unos minutos y ejecuta:
   ```bash
   az containerapp hostname add -g growvia-crm-rg -n growvia-datos --hostname datos.growvia.global
   az containerapp hostname bind -g growvia-crm-rg -n growvia-datos --hostname datos.growvia.global --environment growvia-crm-env --validation-method CNAME
   ```
   Si el certificado falla, es porque el CNAME aún no se propagó. Espera y vuelve a intentar.

## Publicar una versión nueva
```bash
# Pasos 0 y 3, y luego:
az containerapp update -g growvia-crm-rg -n growvia-datos --image growviaregistry.azurecr.io/growvia-datos:$TAG
az containerapp revision list -g growvia-crm-rg -n growvia-datos -o table
```

## Cambiar algo
- **Pasar al plan Plus de apiconsulta:**
  ```bash
  az containerapp update -g growvia-crm-rg -n growvia-datos --set-env-vars APICONSULTA_LIMITE_MES=100000
  ```
- **Cambiar el token:** ejecuta `read -s API_TOKEN` en una línea aparte. Luego:
  ```bash
  az containerapp secret set -g growvia-crm-rg -n growvia-datos --secrets apiconsulta-token="$API_TOKEN"
  unset API_TOKEN
  ```
  Después reinicia la revisión.
- **Registros:**
  ```bash
  az containerapp logs show -g growvia-crm-rg -n growvia-datos --tail 100
  ```

## Limpiar el CRM (después de unir el PR #28 del CRM)
El CRM ya no usa apiconsulta. Antes de borrar su secreto, crea esta app: el paso 2 lo copia del CRM. Después:
```bash
az containerapp update -g growvia-crm-rg -n growvia-crm --remove-env-vars APICONSULTA_TOKEN APICONSULTA_MAX_DIA APICONSULTA_URL
az containerapp secret remove -g growvia-crm-rg -n growvia-crm --secret-names apiconsulta-token
```
