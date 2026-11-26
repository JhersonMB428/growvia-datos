"""Configuración por variables de entorno. Los secretos nunca se escriben en el repositorio."""
import os


def _lista(nombre: str) -> list[str]:
    return [x.strip().lower() for x in os.environ.get(nombre, '').split(',') if x.strip()]


DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres@localhost:5432/growvia_datos')
JWT_SECRETO = os.environ.get('JWT_SECRETO', '')
PRODUCCION = os.environ.get('ENTORNO', 'desarrollo') == 'produccion'

# Correos que siempre son administradores (se crean al arrancar si no existen)
ADMIN_INICIAL = _lista('ADMIN_INICIAL')

# Correo (mismo SMTP que el CRM). Sin SMTP_HOST, el código se muestra en el registro del servidor.
SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
CORREO_REMITENTE = os.environ.get('CORREO_REMITENTE', 'Growvia Datos <no-responder@growvia.global>')

# apiconsulta.dev
APICONSULTA_URL = os.environ.get('APICONSULTA_URL', 'https://api.apiconsulta.dev').rstrip('/')
APICONSULTA_TOKEN = os.environ.get('APICONSULTA_TOKEN', '')
# Consultas que da el plan contratado al mes (gratis: 100, Plus: 100000)
APICONSULTA_LIMITE_MES = int(os.environ.get('APICONSULTA_LIMITE_MES', '100'))
# Una respuesta guardada se reutiliza durante estos días (no se paga dos veces la misma consulta)
DIAS_CACHE = int(os.environ.get('DIAS_CACHE', '60'))

# Padrón reducido de SUNAT (gratis)
PADRON_URL = os.environ.get('PADRON_URL', 'http://www2.sunat.gob.pe/padron_reducido_ruc.zip')
PADRON_CARPETA = os.environ.get('PADRON_CARPETA', '/tmp/padron')
PADRON_DIAS = int(os.environ.get('PADRON_DIAS', '7'))
# Copia del padrón en Azure Blob (para no descargarlo de SUNAT cada vez que la app arranca)
AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING', '')
PADRON_CONTENEDOR = os.environ.get('PADRON_CONTENEDOR', 'padron')

CARPETA_FRONTEND = os.environ.get('CARPETA_FRONTEND', os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'dist'))
