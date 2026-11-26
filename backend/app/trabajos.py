"""Bases subidas: buscar RUC → revisar → consultar SUNAT → revisar → descargar en la plantilla del CRM."""
import json
import logging
import os
import re
import threading
import time
import uuid
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from . import apiconsulta, config, db, excel, padron
from .auth import solo_admin, usuario_actual
from .normalizar import nombre_propio, normal, ruc_valido, solo_digitos, telefono, texto

log = logging.getLogger('trabajos')
router = APIRouter(prefix='/api', tags=['trabajos'])

with open(os.path.join(os.path.dirname(__file__), 'ubigeo.json'), encoding='utf-8') as _f:
    UBIGEO: dict[str, list[str]] = json.load(_f)

CONFIABLES = ('DEL_ARCHIVO', 'EXACTO', 'ELEGIDO')
DUDOSOS = ('PROBABLE', 'VARIOS', 'NO_ENCONTRADO', 'INVALIDO')
SEGMENTOS = ('Micro', 'Pequeña', 'Mediana', 'Grande')
_hilos: dict[str, threading.Thread] = {}


# ───────────────────────── Datos finales de una fila ─────────────────────────
def _operador(v: str) -> str:
    n = normal(v)
    for o in excel.OPERADORES:
        if o.upper() in n:
            return o
    if 'TELEFONICA' in n:
        return 'Movistar'
    if 'AMERICA MOVIL' in n:
        return 'Claro'
    return ''


def _entero(v):
    d = solo_digitos(v)
    return int(d) if d and len(d) <= 6 else None


def final(f: dict) -> dict:
    """Lo que irá al CRM. Gana lo revisado a mano; luego SUNAT (representante, razón social, ubicación); luego el archivo."""
    o, d, p, s = f['original'] or {}, f['datos'] or {}, f['padron'] or {}, f['sunat'] or {}
    reps = s.get('representantes') or []
    rep = reps[d['rep']] if isinstance(d.get('rep'), int) and d['rep'] < len(reps) else (reps[0] if reps else None)
    tels, correos = s.get('telefonos') or [], s.get('correos') or []

    ub = UBIGEO.get(p.get('ubigeo') or '')
    if ub:
        dep, prov, dist = ub
    else:
        dep, prov, dist = (nombre_propio(o.get(k, '')) for k in ('departamento', 'provincia', 'distrito'))

    tel_archivo, correo_archivo = telefono(o.get('telefono')), (o.get('correo') or '').strip().lower()
    tel = d['telefono'] if 'telefono' in d else (tel_archivo or (tels[0] if tels else ''))
    cor = d['correo'] if 'correo' in d else (correo_archivo or (correos[0] if correos else ''))

    # Líneas: por operador (revisado a mano → columnas del archivo) o el total del archivo
    lineas_por = {k: v for k, v in (d.get('lineas_por') or {}).items() if v is not None} if 'lineas_por' in d else \
        {op.lower(): _entero(o.get(f'lineas_{op.lower()}')) for op in excel.OPERADORES if _entero(o.get(f'lineas_{op.lower()}')) is not None}
    if lineas_por:
        total = sum(lineas_por.values())
        operador = max(lineas_por, key=lambda k: lineas_por[k]).capitalize() if total else ''
    else:
        total, operador = _entero(o.get('lineas')), _operador(o.get('operador', ''))

    trab = s.get('trabajadores') or {}
    estimado = apiconsulta.tamano(trab.get('trabajadores'))
    segmento = d.get('segmento') or (o.get('segmento') if o.get('segmento') in SEGMENTOS else '') or estimado

    if 'representante' in d:
        nombre_rep, dni, cargo = d['representante'], d.get('dni', ''), d.get('cargo', '')
    elif rep:
        nombre_rep, dni, cargo = rep['nombre'], rep['dni'], rep['cargo']
    else:
        nombre_rep, dni, cargo = nombre_propio(o.get('contacto', '')), solo_digitos(o.get('dni'))[:8], ''

    return {
        'ruc': f['ruc'] or '', 'razon': p.get('razon') or o.get('razon', ''),
        'representante': nombre_rep, 'dni': dni, 'cargo': cargo,
        'telefono': tel, 'correo': cor,
        'departamento': dep, 'provincia': prov, 'distrito': dist,
        'lineas': total, 'operador': operador, 'lineas_por': lineas_por,
        'segmento': segmento, 'segmento_estimado': estimado,
        'trabajadores': trab.get('trabajadores'), 'periodo': trab.get('periodo', ''),
        'estado_sunat': ' · '.join(x for x in (p.get('estado'), p.get('condicion')) if x),
        'activo': (p.get('estado') or 'ACTIVO') == 'ACTIVO',
        'otros_telefonos': [t for t in tels if t != tel][:4], 'otros_correos': [c for c in correos if c != cor][:3],
        'direccion': p.get('direccion', ''), 'nombre_archivo': o.get('razon', ''),
        'como_ruc': ETIQUETA_RUC.get(f['ruc_estado'] or '', ''), 'observacion': d.get('observacion', ''),
        'extra': f['extra'] or {},
    }


ETIQUETA_RUC = {
    'DEL_ARCHIVO': 'Venía en el archivo', 'EXACTO': 'Nombre exacto en SUNAT', 'ELEGIDO': 'Elegido a mano',
    'PROBABLE': 'Probable (revisar)', 'VARIOS': 'Varios posibles', 'NO_ENCONTRADO': 'No encontrado', 'INVALIDO': 'RUC no válido',
    'DESCARTADA': 'Descartada',
}


def _faltantes(x: dict) -> list[str]:
    nombres = [('ruc', 'RUC'), ('razon', 'razón social'), ('representante', 'representante'), ('dni', 'DNI'),
               ('telefono', 'teléfono'), ('distrito', 'ubicación'), ('lineas', 'líneas'), ('operador', 'operador')]
    return [t for k, t in nombres if x.get(k) in (None, '')]


def _fila_api(f: dict) -> dict:
    x = final(f)
    return {'id': f['id'], 'n': f['n'], 'rucEstado': f['ruc_estado'], 'opciones': f['opciones'], 'consultada': f['consultada'],
            'representantes': (f['sunat'] or {}).get('representantes') or [], 'datos': f['datos'] or {},
            'original': f['original'] or {}, 'final': {k: v for k, v in x.items() if k != 'extra'}, 'faltan': _faltantes(x)}


# ───────────────────────── Procesos en segundo plano ─────────────────────────
def _estado(tid: str, estado: str | None = None, mensaje: str | None = None, progreso: int | None = None, total: int | None = None):
    db.ejecutar('UPDATE trabajos SET estado = COALESCE(%s, estado), mensaje = %s, progreso = COALESCE(%s, progreso), '
                'total = COALESCE(%s, total), actualizado_at = now() WHERE id = %s', (estado, mensaje, progreso, total, tid))


def _lanzar(tid: str, funcion, *args):
    if tid in _hilos and _hilos[tid].is_alive():
        return
    h = threading.Thread(target=funcion, args=(tid, *args), daemon=True, name=f'trabajo-{tid}')
    _hilos[tid] = h
    h.start()


def buscar_rucs(tid: str):
    try:
        filas = db.todos('SELECT id, original, ruc FROM filas WHERE trabajo_id = %s AND ruc_estado IS NULL', (tid,))
        rucs, nombres = set(), {}
        for f in filas:
            o = f['original']
            if o.get('ruc'):
                if ruc_valido(o['ruc']):
                    rucs.add(o['ruc'])
            elif o.get('razon'):
                nombres[f['id']] = o['razon']
        if not rucs and not nombres:
            por_ruc, cands = {}, {}
        else:
            ruta = padron.asegurar(lambda t: _estado(tid, 'BUSCANDO_RUC', t))
            _estado(tid, 'BUSCANDO_RUC', 'Buscando en el padrón de SUNAT…', 0)
            por_ruc, cands = padron.escanear(ruta, rucs, nombres,
                                             lambda i: _estado(tid, mensaje=f'Buscando en el padrón de SUNAT… {i / 1e6:.1f} millones revisados'))
        with db.conexion() as c:
            for f in filas:
                o = f['original']
                if o.get('ruc'):
                    if not ruc_valido(o['ruc']):
                        estado, ruc, ops, dato = 'INVALIDO', o['ruc'], [], None
                    else:
                        estado, ruc, ops, dato = 'DEL_ARCHIVO', o['ruc'], [], por_ruc.get(o['ruc'])
                elif f['id'] in nombres:
                    ruc, estado, ops = padron.elegir(cands.get(f['id'], []))
                    dato = next((x for x in ops if x['ruc'] == ruc), None)
                else:
                    estado, ruc, ops, dato = 'NO_ENCONTRADO', None, [], None
                limpio = lambda x: {k: v for k, v in x.items() if k not in ('exacto', 'sobra')} if x else None
                c.execute('UPDATE filas SET ruc = %s, ruc_estado = %s, opciones = %s, padron = %s WHERE id = %s',
                          (ruc, estado, db.j([limpio(x) for x in ops]), db.j(limpio(dato)), f['id']))
        _estado(tid, 'REVISAR_RUC', None)
    except Exception as e:
        log.exception('Falló la búsqueda de RUC')
        _estado(tid, 'ERROR', f'No se pudo buscar en el padrón de SUNAT: {e}. Usa "Reintentar".')


def consultar(tid: str, usuario_id: int):
    try:
        t = db.uno('SELECT endpoints FROM trabajos WHERE id = %s', (tid,))
        endpoints = t['endpoints'] or list(apiconsulta.ENDPOINTS)
        filas = db.todos("SELECT id, ruc, sunat FROM filas WHERE trabajo_id = %s AND NOT consultada AND (datos->>'_consultar')::boolean ORDER BY n", (tid,))
        _estado(tid, 'CONSULTANDO', 'Consultando SUNAT…', 0, len(filas))
        with httpx.Client(timeout=25) as cliente:
            for i, f in enumerate(filas, start=1):
                s = dict(f['sunat'] or {})
                if 'representantes' in endpoints:
                    s['representantes'] = apiconsulta.representantes(apiconsulta.consultar(cliente, f['ruc'], 'representantes', usuario_id, tid))
                if 'contacto' in endpoints:
                    s.update(apiconsulta.contacto(apiconsulta.consultar(cliente, f['ruc'], 'contacto', usuario_id, tid)))
                if 'trabajadores' in endpoints:
                    s['trabajadores'] = apiconsulta.trabajadores(apiconsulta.consultar(cliente, f['ruc'], 'trabajadores', usuario_id, tid))
                db.ejecutar("UPDATE filas SET sunat = %s, consultada = true, datos = datos - '_consultar' WHERE id = %s", (db.j(s), f['id']))
                _estado(tid, mensaje=f'Consultando SUNAT… {i} de {len(filas)}', progreso=i)
                time.sleep(0.15)
        db.ejecutar("UPDATE filas SET datos = datos - '_consultar' WHERE trabajo_id = %s", (tid,))
        _estado(tid, 'REVISION', None)
        db.registrar(usuario_id, 'CONSULTA_TERMINADA', {'trabajo': tid, 'empresas': len(filas)})
    except apiconsulta.SinConsultas as e:
        _estado(tid, 'REVISION', f'Se detuvo: {e} Las empresas que faltan se pueden consultar después.')
    except Exception as e:
        log.exception('Falló la consulta a SUNAT')
        _estado(tid, 'REVISION', f'Se detuvo por un error ({e}). Las empresas que faltan se pueden consultar después.')


def reanudar():
    """Al arrancar, retoma lo que quedó a medias (la app se apaga sola si nadie la usa)"""
    for t in db.todos("SELECT id, estado, creado_por FROM trabajos WHERE estado IN ('BUSCANDO_RUC', 'CARGADO', 'CONSULTANDO')"):
        tid = str(t['id'])
        if t['estado'] == 'CONSULTANDO':
            _lanzar(tid, consultar, t['creado_por'])
        else:
            _lanzar(tid, buscar_rucs)


# ───────────────────────── Rutas ─────────────────────────
def _trabajo(tid: str) -> dict:
    try:
        uuid.UUID(tid)
    except ValueError:
        raise HTTPException(404, 'La base no existe')
    t = db.uno('''SELECT t.id, t.nombre, t.archivo, t.estado, t.progreso, t.total, t.mensaje, t.columnas_extra AS "columnasExtra",
                         t.endpoints, t.descargas, t.creado_at AS "creadoAt", t.actualizado_at AS "actualizadoAt",
                         t.creado_por AS "creadoPorId", u.email AS "creadoPor"
                  FROM trabajos t JOIN usuarios u ON u.id = t.creado_por WHERE t.id = %s''', (tid,))
    if not t:
        raise HTTPException(404, 'La base no existe')
    return t


@router.get('/trabajos')
def listar(_: dict = Depends(usuario_actual)):
    return db.todos('''SELECT t.id, t.nombre, t.archivo, t.estado, t.mensaje, t.progreso, t.total, t.descargas,
                              t.creado_at AS "creadoAt", u.email AS "creadoPor",
                              count(f.id) AS filas,
                              count(f.id) FILTER (WHERE f.ruc_estado IN ('DEL_ARCHIVO', 'EXACTO', 'ELEGIDO')) AS "conRuc",
                              count(f.id) FILTER (WHERE f.ruc_estado IN ('PROBABLE', 'VARIOS', 'NO_ENCONTRADO', 'INVALIDO')) AS "porRevisar",
                              count(f.id) FILTER (WHERE f.consultada) AS consultadas
                       FROM trabajos t JOIN usuarios u ON u.id = t.creado_por LEFT JOIN filas f ON f.trabajo_id = t.id
                       GROUP BY t.id, u.email ORDER BY t.creado_at DESC LIMIT 100''')


@router.post('/trabajos')
async def subir(archivo: UploadFile = File(...), nombre: str = Form(''), u: dict = Depends(usuario_actual)):
    if not (archivo.filename or '').lower().endswith(('.xlsx', '.xlsm')):
        raise HTTPException(400, 'Sube la base como Excel (.xlsx)')
    contenido = await archivo.read()
    if len(contenido) > 15 * 1024 * 1024:
        raise HTTPException(400, 'El archivo pesa más de 15 MB')
    try:
        filas, extras = excel.leer(contenido)
    except excel.ErrorArchivo as e:
        raise HTTPException(400, str(e))
    nombre = (nombre or os.path.splitext(archivo.filename)[0]).strip()[:120]
    with db.conexion() as c:
        t = c.execute('INSERT INTO trabajos (nombre, archivo, creado_por, columnas_extra, total, estado) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                      (nombre, archivo.filename[:200], u['id'], db.j(extras), len(filas), 'BUSCANDO_RUC')).fetchone()
        tid = str(t['id'])
        with c.cursor() as cur:
            cur.executemany('INSERT INTO filas (trabajo_id, n, original, extra) VALUES (%s, %s, %s, %s)',
                            [(tid, f['n'], db.j(f['original']), db.j(f['extra'])) for f in filas])
    db.registrar(u['id'], 'BASE_SUBIDA', {'trabajo': tid, 'archivo': archivo.filename, 'filas': len(filas)})
    _lanzar(tid, buscar_rucs)
    return {'id': tid}


@router.get('/trabajos/{tid}')
def detalle(tid: str, _: dict = Depends(usuario_actual)):
    t = _trabajo(tid)
    filas = db.todos('SELECT * FROM filas WHERE trabajo_id = %s ORDER BY n', (tid,))
    t['filas'] = [_fila_api(f) for f in filas]
    return t


@router.post('/trabajos/{tid}/reintentar')
def reintentar(tid: str, u: dict = Depends(usuario_actual)):
    t = _trabajo(tid)
    if t['estado'] != 'ERROR':
        raise HTTPException(400, 'Esta base no tiene nada que reintentar')
    _estado(tid, 'BUSCANDO_RUC', 'Reintentando…')
    _lanzar(tid, buscar_rucs)
    return {'ok': True}


class ElegirRuc(BaseModel):
    ruc: str | None = None
    descartar: bool = False


@router.post('/trabajos/{tid}/filas/{fid}/ruc')
def elegir_ruc(tid: str, fid: int, dto: ElegirRuc, u: dict = Depends(usuario_actual)):
    _trabajo(tid)
    f = db.uno('SELECT id, opciones, ruc, ruc_estado, consultada FROM filas WHERE id = %s AND trabajo_id = %s', (fid, tid))
    if not f:
        raise HTTPException(404, 'La fila no existe')
    if dto.descartar:
        db.ejecutar("UPDATE filas SET ruc_estado = 'DESCARTADA' WHERE id = %s", (fid,))
        return {'ok': True}
    ruc = solo_digitos(dto.ruc)
    if not ruc_valido(ruc):
        raise HTTPException(400, 'Ese RUC no es válido: revisa los 11 dígitos')
    dato = next((x for x in f['opciones'] if x['ruc'] == ruc), None)
    cambio = ruc != f['ruc']
    db.ejecutar("UPDATE filas SET ruc = %s, ruc_estado = 'ELEGIDO', padron = COALESCE(%s, CASE WHEN %s THEN NULL ELSE padron END), "
                "consultada = consultada AND NOT %s, sunat = CASE WHEN %s THEN NULL ELSE sunat END WHERE id = %s",
                (ruc, db.j(dato) if dato else None, cambio, cambio, cambio, fid))
    return {'ok': True}


class Consulta(BaseModel):
    endpoints: list[str] = list(apiconsulta.ENDPOINTS)
    incluirProbables: bool = False
    excluirInactivas: bool = True
    limite: int | None = None
    confirmar: bool = False


def _por_consultar(tid: str, dto: Consulta) -> list[dict]:
    estados = list(CONFIABLES) + (['PROBABLE'] if dto.incluirProbables else [])
    filas = db.todos('SELECT id, ruc, padron FROM filas WHERE trabajo_id = %s AND ruc_estado = ANY(%s) AND NOT consultada ORDER BY n', (tid, estados))
    filas = [f for f in filas if f['ruc'] and ruc_valido(f['ruc'])
             and not (dto.excluirInactivas and f['padron'] and f['padron'].get('estado') not in (None, '', 'ACTIVO'))]
    return filas[:dto.limite] if dto.limite else filas


@router.post('/trabajos/{tid}/consultar')
def iniciar_consulta(tid: str, dto: Consulta, u: dict = Depends(usuario_actual)):
    t = _trabajo(tid)
    if t['estado'] not in ('REVISAR_RUC', 'REVISION'):
        raise HTTPException(400, 'Espera a que termine el paso anterior')
    endpoints = [e for e in dto.endpoints if e in apiconsulta.ENDPOINTS]
    if not endpoints:
        raise HTTPException(400, 'Elige al menos un dato para consultar')
    filas = _por_consultar(tid, dto)
    gasto = sum(len(apiconsulta.faltan(f['ruc'], endpoints)) for f in filas)
    usadas = apiconsulta.usadas_mes()
    quedan = max(0, config.APICONSULTA_LIMITE_MES - usadas)
    estimado = {'empresas': len(filas), 'consultas': gasto, 'usadasMes': usadas, 'limiteMes': config.APICONSULTA_LIMITE_MES,
                'quedan': quedan, 'alcanza': gasto <= quedan, 'tokenActivo': apiconsulta.activo()}
    if not dto.confirmar:
        return estimado
    if not apiconsulta.activo():
        raise HTTPException(400, 'Falta configurar el token de apiconsulta (lo hace el administrador en Azure)')
    if not filas:
        raise HTTPException(400, 'No hay empresas por consultar con esas opciones')
    if gasto > quedan:
        raise HTTPException(400, f'Esta consulta gastaría {gasto} consultas y solo quedan {quedan} este mes. Usa un límite de empresas o pasa al plan Plus.')
    with db.conexion() as c:
        c.execute('UPDATE trabajos SET endpoints = %s WHERE id = %s', (db.j(endpoints), tid))
        c.execute("UPDATE filas SET datos = datos || '{\"_consultar\": true}' WHERE id = ANY(%s)", ([f['id'] for f in filas],))
    db.registrar(u['id'], 'CONSULTA_INICIADA', {'trabajo': tid, 'empresas': len(filas), 'consultas': gasto, 'endpoints': endpoints})
    _estado(tid, 'CONSULTANDO', 'Empezando…', 0, len(filas))
    _lanzar(tid, consultar, u['id'])
    return estimado


class EditarFila(BaseModel):
    rep: int | None = None
    representante: str | None = None
    dni: str | None = None
    cargo: str | None = None
    telefono: str | None = None
    correo: str | None = None
    segmento: str | None = None
    lineas_por: dict[str, int | None] | None = None
    observacion: str | None = None
    quitar: list[str] = []


@router.patch('/trabajos/{tid}/filas/{fid}')
def editar_fila(tid: str, fid: int, dto: EditarFila, u: dict = Depends(usuario_actual)):
    _trabajo(tid)
    f = db.uno('SELECT * FROM filas WHERE id = %s AND trabajo_id = %s', (fid, tid))
    if not f:
        raise HTTPException(404, 'La fila no existe')
    d = dict(f['datos'] or {})
    cambios = dto.model_dump(exclude_unset=True, exclude={'quitar'})
    if 'dni' in cambios and cambios['dni'] and not re.fullmatch(r'\d{8}', cambios['dni']):
        raise HTTPException(400, 'El DNI tiene 8 dígitos')
    if 'telefono' in cambios and cambios['telefono'] and not telefono(cambios['telefono']):
        raise HTTPException(400, 'Revisa el teléfono')
    if 'correo' in cambios and cambios['correo'] and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}', cambios['correo'].strip()):
        raise HTTPException(400, 'Revisa el correo')
    if cambios.get('segmento') and cambios['segmento'] not in SEGMENTOS:
        raise HTTPException(400, 'Segmento no válido')
    if 'lineas_por' in cambios and cambios['lineas_por'] is not None:
        lp = {k.lower(): v for k, v in cambios['lineas_por'].items() if k.capitalize() in excel.OPERADORES}
        if any(v is not None and not (0 <= v <= 100000) for v in lp.values()):
            raise HTTPException(400, 'Revisa la cantidad de líneas')
        cambios['lineas_por'] = lp
    if 'rep' in cambios:  # elegir otro representante de SUNAT borra lo escrito a mano
        for k in ('representante', 'dni', 'cargo'):
            d.pop(k, None)
    if 'telefono' in cambios and cambios['telefono']:
        cambios['telefono'] = telefono(cambios['telefono'])
    if 'correo' in cambios and cambios['correo']:
        cambios['correo'] = cambios['correo'].strip().lower()
    for k, v in cambios.items():
        if isinstance(v, str):
            v = v.strip()[:200]
        d[k] = v
    for k in dto.quitar:
        d.pop(k, None)
    db.ejecutar('UPDATE filas SET datos = %s WHERE id = %s', (db.j(d), fid))
    f['datos'] = d
    return _fila_api(f)


@router.get('/trabajos/{tid}/excel')
def descargar(tid: str, segmento: str = 'todos', solo_listas: bool = True, incluir_inactivas: bool = False, u: dict = Depends(usuario_actual)):
    t = _trabajo(tid)
    filas = []
    for f in db.todos('SELECT * FROM filas WHERE trabajo_id = %s ORDER BY n', (tid,)):
        if f['ruc_estado'] == 'DESCARTADA':
            continue
        if solo_listas and f['ruc_estado'] not in CONFIABLES:
            continue
        x = final(f)
        if not incluir_inactivas and not x['activo']:
            continue
        if segmento == 'micro' and x['segmento'] != 'Micro':
            continue
        if segmento == 'pyme' and x['segmento'] not in ('Pequeña', 'Mediana'):
            continue
        if segmento == 'grande' and x['segmento'] != 'Grande':
            continue
        if segmento == 'sin' and x['segmento']:
            continue
        filas.append(x)
    if not filas:
        raise HTTPException(400, 'No hay empresas con esos filtros')
    contenido = excel.generar(filas, t['columnasExtra'] or [])
    db.ejecutar('UPDATE trabajos SET descargas = descargas + 1 WHERE id = %s', (tid,))
    db.registrar(u['id'], 'EXCEL_DESCARGADO', {'trabajo': tid, 'filas': len(filas), 'segmento': segmento})
    nombre = f"{re.sub(r'[^A-Za-z0-9 _-]', '', t['nombre']).strip() or 'base'} - CRM{'' if segmento == 'todos' else ' - ' + segmento}.xlsx"
    return Response(contenido, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(nombre)}"})


@router.delete('/trabajos/{tid}')
def borrar(tid: str, u: dict = Depends(usuario_actual)):
    t = _trabajo(tid)
    if t['creadoPorId'] != u['id'] and u['rol'] != 'ADMIN':
        raise HTTPException(403, 'Solo quien subió la base o un administrador pueden borrarla')
    if t['estado'] in ('BUSCANDO_RUC', 'CONSULTANDO'):
        raise HTTPException(400, 'Espera a que termine el proceso para borrarla')
    db.ejecutar('DELETE FROM trabajos WHERE id = %s', (tid,))
    db.registrar(u['id'], 'BASE_BORRADA', {'nombre': t['nombre']})
    return {'ok': True}


# ───────────────────────── Consumo y padrón ─────────────────────────
@router.get('/consumo')
def consumo(_: dict = Depends(usuario_actual)):
    return {
        'usadasMes': apiconsulta.usadas_mes(), 'limiteMes': config.APICONSULTA_LIMITE_MES, 'tokenActivo': apiconsulta.activo(),
        'porDia': db.todos('''SELECT (creado_at AT TIME ZONE 'America/Lima')::date AS dia, count(*) FILTER (WHERE NOT desde_cache) AS pagadas,
                                     count(*) FILTER (WHERE desde_cache) AS reutilizadas
                              FROM consultas WHERE creado_at > now() - interval '60 days' GROUP BY 1 ORDER BY 1'''),
        'porEndpoint': db.todos('''SELECT endpoint, count(*) AS pagadas FROM consultas WHERE NOT desde_cache
                                    AND creado_at >= date_trunc('month', now() AT TIME ZONE 'America/Lima') AT TIME ZONE 'America/Lima' GROUP BY 1 ORDER BY 2 DESC'''),
        'porUsuario': db.todos('''SELECT u.email, count(*) FILTER (WHERE NOT c.desde_cache) AS pagadas, count(*) FILTER (WHERE c.desde_cache) AS reutilizadas
                                   FROM consultas c LEFT JOIN usuarios u ON u.id = c.usuario_id
                                   WHERE c.creado_at >= date_trunc('month', now() AT TIME ZONE 'America/Lima') AT TIME ZONE 'America/Lima'
                                   GROUP BY u.email ORDER BY 2 DESC'''),
        'padron': padron.info(),
    }


@router.post('/padron/actualizar')
def actualizar_padron(u: dict = Depends(solo_admin)):
    def tarea():
        try:
            padron.asegurar(forzar=True)
        except Exception:
            log.exception('No se pudo actualizar el padrón')
    threading.Thread(target=tarea, daemon=True).start()
    db.registrar(u['id'], 'PADRON_ACTUALIZADO')
    return {'mensaje': 'Se está descargando el padrón de SUNAT. Tarda unos minutos.'}
