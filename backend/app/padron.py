"""
Padrón reducido de SUNAT (gratis): RUC, razón social, estado, condición, ubigeo y dirección de todos los contribuyentes.
Se descarga de SUNAT una vez por semana y se guarda una copia en Azure Blob para no bajarlo en cada arranque.
"""
import io
import logging
import os
import shutil
import threading
import time
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

from . import config, db
from .normalizar import COMUNES, claves, normal, palabras_rapidas

log = logging.getLogger('padron')
_candado = threading.Lock()
NOMBRE = 'padron_reducido_ruc.zip'


def _ruta() -> str:
    return os.path.join(config.PADRON_CARPETA, NOMBRE)


def _vigente(ruta: str) -> bool:
    return os.path.exists(ruta) and time.time() - os.path.getmtime(ruta) < config.PADRON_DIAS * 86400


def _blob():
    if not config.AZURE_STORAGE_CONNECTION_STRING:
        return None
    from azure.storage.blob import BlobServiceClient
    servicio = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
    contenedor = servicio.get_container_client(config.PADRON_CONTENEDOR)
    if not contenedor.exists():
        contenedor.create_container()
    return contenedor.get_blob_client(NOMBRE)


def info() -> dict:
    return db.ajuste('padron', {}) or {}


def asegurar(avisar=lambda texto: None, forzar: bool = False) -> str:
    """Devuelve la ruta del .zip vigente: disco → copia en Azure → SUNAT"""
    with _candado:
        ruta = _ruta()
        if _vigente(ruta) and not forzar:
            return ruta
        os.makedirs(config.PADRON_CARPETA, exist_ok=True)
        temporal = ruta + '.tmp'
        blob = None
        try:
            blob = _blob()
            if blob and not forzar and blob.exists():
                props = blob.get_blob_properties()
                edad = (datetime.now(timezone.utc) - props.last_modified).total_seconds()
                if edad < config.PADRON_DIAS * 86400:
                    avisar('Trayendo el padrón de SUNAT guardado…')
                    with open(temporal, 'wb') as f:
                        blob.download_blob(max_concurrency=4).readinto(f)
                    os.replace(temporal, ruta)
                    os.utime(ruta, (props.last_modified.timestamp(), props.last_modified.timestamp()))
                    if not info().get('descargado'):
                        db.guardar_ajuste('padron', {'descargado': props.last_modified.isoformat(), 'tamano': os.path.getsize(ruta)})
                    return ruta
        except Exception:  # sin Azure se descarga directo de SUNAT
            log.exception('No se pudo usar la copia del padrón en Azure')

        avisar('Descargando el padrón de SUNAT (unos 400 MB, tarda unos minutos)…')
        pedido = urllib.request.Request(config.PADRON_URL, headers={'User-Agent': 'Mozilla/5.0 (Growvia Datos)'})
        with urllib.request.urlopen(pedido, timeout=120) as r, open(temporal, 'wb') as f:
            shutil.copyfileobj(r, f, length=1024 * 1024)
        with zipfile.ZipFile(temporal) as z:  # que sea un zip válido antes de reemplazar
            if not any(n.lower().endswith('.txt') for n in z.namelist()):
                raise RuntimeError('El archivo descargado de SUNAT no trae el padrón')
        os.replace(temporal, ruta)
        db.guardar_ajuste('padron', {'descargado': datetime.now(timezone.utc).isoformat(), 'tamano': os.path.getsize(ruta)})
        try:
            if blob:
                with open(ruta, 'rb') as f:
                    blob.upload_blob(f, overwrite=True, max_concurrency=4)
        except Exception:
            log.exception('No se pudo guardar la copia del padrón en Azure')
        return ruta


def _direccion(p: list[str]) -> str:
    # TIPO DE VÍA|NOMBRE DE VÍA|CÓDIGO DE ZONA|TIPO DE ZONA|NÚMERO|INTERIOR|LOTE|DEPARTAMENTO|MANZANA|KILÓMETRO
    if len(p) < 15:
        return ''
    via = ' '.join(x for x in (p[5], p[6]) if x and x != '-')
    zona = ' '.join(x for x in (p[8], p[7]) if x and x != '-')
    resto = [f'{e} {v}' for e, v in zip(('NRO.', 'INT.', 'LT.', 'DPTO.', 'MZ.', 'KM.'), (p[9], p[10], p[11], p[12], p[13], p[14])) if v and v != '-']
    return ' '.join(x for x in [via, *resto, zona] if x).strip()


def escanear(ruta: str, rucs: set[str], nombres: dict[int, str], avance=lambda n: None) -> tuple[dict, dict]:
    """
    Recorre el padrón una sola vez.
    - rucs: RUC que vinieron en el archivo → devuelve sus datos del padrón.
    - nombres: {id_fila: razón social} sin RUC → devuelve candidatos por fila.
    """
    por_ruc: dict[str, dict] = {}
    candidatos: dict[int, list] = defaultdict(list)
    exactos: dict[str, list[int]] = defaultdict(list)
    por_palabra: dict[str, list[tuple[int, set]]] = defaultdict(list)
    for fid, nombre in nombres.items():
        n = normal(nombre)
        if not n:
            continue
        exactos[n].append(fid)
        k = claves(nombre)
        if k:
            por_palabra[max(k, key=len)].append((fid, k))
    indice = set(por_palabra.keys())

    with zipfile.ZipFile(ruta) as z:
        txt = next(n for n in z.namelist() if n.lower().endswith('.txt'))
        with z.open(txt) as crudo:
            for i, linea in enumerate(io.TextIOWrapper(crudo, encoding='latin-1', errors='replace')):
                if i == 0:
                    continue
                if i % 500_000 == 0:
                    avance(i)
                partes = linea.rstrip('\r\n').split('|')
                if len(partes) < 5:
                    continue
                ruc = partes[0].strip()
                en_rucs = ruc in rucs
                comunes = (palabras_rapidas(partes[1]) & indice) if indice else set()
                if not en_rucs and not comunes:
                    continue
                dato = {'ruc': ruc, 'razon': partes[1].strip(), 'estado': partes[2].strip(), 'condicion': partes[3].strip(),
                        'ubigeo': partes[4].strip(), 'direccion': _direccion([x.strip() for x in partes])}
                if en_rucs:
                    por_ruc[ruc] = dato
                if comunes:
                    n = normal(partes[1])
                    palabras = set(n.split())
                    for fid in exactos.get(n, ()):
                        candidatos[fid].append({**dato, 'exacto': True, 'sobra': 0})
                    for p in comunes:
                        for fid, k in por_palabra[p]:
                            if k <= palabras and n not in exactos:
                                candidatos[fid].append({**dato, 'exacto': False, 'sobra': len(palabras - k - COMUNES)})
                                if len(candidatos[fid]) > 400:  # nombres demasiado genéricos: no seguir juntando
                                    candidatos[fid] = sorted(candidatos[fid], key=lambda x: x['sobra'])[:50]
    return por_ruc, candidatos


def elegir(cands: list[dict]) -> tuple[str | None, str, list[dict]]:
    """(ruc elegido, estado, opciones). Exacto y activo primero; si hay dudas, se revisa a mano."""
    activos = lambda xs: [x for x in xs if x['estado'] == 'ACTIVO'] or xs
    exactos = activos([x for x in cands if x['exacto']])
    if len(exactos) == 1:
        return exactos[0]['ruc'], 'EXACTO', exactos
    if len(exactos) > 1:
        juridicas = [x for x in exactos if x['ruc'].startswith('20')]
        if len(juridicas) == 1:
            return juridicas[0]['ruc'], 'EXACTO', exactos[:5]
        return None, 'VARIOS', exactos[:6]
    parecidos = sorted(activos([x for x in cands if not x['exacto']]), key=lambda x: (x['sobra'], not x['ruc'].startswith('20')))
    if parecidos and (len(parecidos) == 1 or (parecidos[0]['sobra'] <= 1 and parecidos[1]['sobra'] > parecidos[0]['sobra'])):
        return parecidos[0]['ruc'], 'PROBABLE', parecidos[:4]
    return None, ('VARIOS' if parecidos else 'NO_ENCONTRADO'), parecidos[:6]
