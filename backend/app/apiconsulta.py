"""
apiconsulta.dev: representante legal (con DNI), teléfonos y correos declarados a SUNAT, y trabajadores en planilla.
Cada endpoint es una consulta del plan. Una respuesta reciente se reutiliza (caché) y no gasta.
"""
import re
import time

import httpx

from . import config, db
from .normalizar import nombre_propio, solo_digitos, telefono, texto

ENDPOINTS = {
    'empresa': '/ruc',  # solo si el RUC no está en el padrón (se escribió a mano)
    'representantes': '/ruc-representantes',
    'contacto': '/ruc-contacto',
    'trabajadores': '/ruc-trabajadores',
}


class SinConsultas(Exception):
    """El plan se acabó o el token no sirve: se detiene el trabajo"""


def activo() -> bool:
    return bool(config.APICONSULTA_TOKEN)


def usadas_mes() -> int:
    f = db.uno("SELECT count(*) AS n FROM consultas WHERE NOT desde_cache AND creado_at >= date_trunc('month', now() AT TIME ZONE 'America/Lima') AT TIME ZONE 'America/Lima'")
    return int(f['n'])


def en_cache(ruc: str, endpoint: str):
    return db.uno(
        'SELECT respuesta FROM consultas WHERE ruc = %s AND endpoint = %s AND ok AND NOT desde_cache '
        "AND creado_at > now() - make_interval(days => %s) ORDER BY creado_at DESC LIMIT 1",
        (ruc, endpoint, config.DIAS_CACHE))


def faltan(ruc: str, endpoints: list[str]) -> list[str]:
    """Endpoints que de verdad gastarían una consulta (no están en caché)"""
    return [e for e in endpoints if not en_cache(ruc, e)]


def consultar(cliente: httpx.Client, ruc: str, endpoint: str, usuario_id: int, trabajo_id: str):
    guardada = en_cache(ruc, endpoint)
    if guardada:
        db.ejecutar('INSERT INTO consultas (ruc, endpoint, ok, desde_cache, usuario_id, trabajo_id) VALUES (%s, %s, true, true, %s, %s)',
                    (ruc, endpoint, usuario_id, trabajo_id))
        return guardada['respuesta']
    for intento in range(3):
        try:
            r = cliente.post(config.APICONSULTA_URL + ENDPOINTS[endpoint], json={'ruc': ruc},
                             headers={'Authorization': f'Bearer {config.APICONSULTA_TOKEN}', 'Accept': 'application/json'})
        except httpx.HTTPError:
            if intento == 2:
                return None
            time.sleep(2 * (intento + 1))
            continue
        if r.status_code in (401, 403):
            raise SinConsultas('apiconsulta rechazó el token. Pide al administrador que lo revise.')
        if r.status_code == 429:
            raise SinConsultas('Se acabaron las consultas del plan de apiconsulta (o se superó el límite por minuto).')
        if r.status_code >= 500:
            time.sleep(2 * (intento + 1))
            continue
        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = {}
        ok = r.status_code == 200 and cuerpo.get('success', True) is not False
        datos = cuerpo.get('data') if ok else None
        db.ejecutar('INSERT INTO consultas (ruc, endpoint, ok, respuesta, usuario_id, trabajo_id) VALUES (%s, %s, %s, %s, %s, %s)',
                    (ruc, endpoint, ok and datos is not None, db.j(datos), usuario_id, trabajo_id))
        return datos
    return None


# ───────── Resumir respuestas ─────────
def _lista(d, clave: str):
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        if isinstance(d.get(clave), list):
            return d[clave]
        return next((v for v in d.values() if isinstance(v, list)), [d] if d else [])
    return []


def _prioridad(r: dict) -> int:
    cargo = texto(r.get('cargo')).upper()
    if 'GERENTE GENERAL' in cargo:
        return 0
    if 'GERENTE' in cargo or 'TITULAR' in cargo:
        return 1
    if re.search('PRESIDENTE|ADMINISTRADOR|APODERADO', cargo):
        return 2
    return 3


def representantes(d) -> list[dict]:
    salida = []
    for r in _lista(d, 'representantes'):
        if not isinstance(r, dict) or not texto(r.get('nombre')):
            continue
        doc = solo_digitos(r.get('numero_de_documento') or r.get('documento'))
        tipo = texto(r.get('tipo_de_documento')).upper()
        salida.append({
            'nombre': nombre_propio(texto(r.get('nombre'))),
            'dni': doc if len(doc) == 8 and ('DNI' in tipo or 'IDENTIDAD' in tipo or not tipo) else '',
            'documento': doc, 'tipo': tipo,
            'cargo': nombre_propio(texto(r.get('cargo'))),
            'desde': texto(r.get('fecha_desde')),
            'prioridad': _prioridad(r),
        })
    return sorted(salida, key=lambda x: (x['prioridad'], x['desde'] or '9999'))


def empresa(d) -> dict | None:
    """Datos básicos con la misma forma que el padrón (para RUC escritos a mano)"""
    d = d[0] if isinstance(d, list) and d else d
    if not isinstance(d, dict):
        return None
    u = d.get('ubigeo')
    ubigeo = solo_digitos(u.get('ubigeo') if isinstance(u, dict) else u).zfill(6) if u else ''
    return {'ruc': solo_digitos(d.get('ruc')), 'razon': texto(d.get('nombre_o_razon_social') or d.get('razon_social')),
            'estado': texto(d.get('estado')).upper(), 'condicion': texto(d.get('condicion')).upper(),
            'ubigeo': ubigeo, 'direccion': texto(d.get('direccion'))}


def contacto(d) -> dict:
    d = d if isinstance(d, dict) else {}
    tels = []
    for t in d.get('telefonos') or []:
        x = telefono(t)
        if x and x not in tels:
            tels.append(x)
    # Celulares primero
    tels.sort(key=lambda x: not (len(x) == 9 and x[0] == '9'))
    correos = []
    for c in d.get('correos') or []:
        x = texto(c).lower()
        if re.fullmatch(r'[^@\s]+@[^@\s]+\.[a-z]{2,}', x) and x not in correos:
            correos.append(x)
    return {'telefonos': tels, 'correos': correos}


def trabajadores(d) -> dict:
    """El periodo más reciente con su cantidad de trabajadores en planilla"""
    filas = [x for x in _lista(d, 'trabajadores') if isinstance(x, dict)]
    if not filas:
        return {}
    filas.sort(key=lambda x: texto(x.get('periodo')), reverse=True)
    f = filas[0]
    n = solo_digitos(f.get('trabajadores'))
    return {'periodo': texto(f.get('periodo')), 'trabajadores': int(n) if n else None,
            'prestadores': int(solo_digitos(f.get('prestadores_servicio')) or 0)}


def tamano(n: int | None) -> str:
    """Estimado por trabajadores en planilla (no por ventas)"""
    if n is None:
        return ''
    if n <= 10:
        return 'Micro'
    if n <= 100:
        return 'Pequeña'
    if n <= 250:
        return 'Mediana'
    return 'Grande'
