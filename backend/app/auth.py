"""Ingreso con código al correo. Solo entran los correos que un administrador autorizó."""
import hashlib
import hmac
import logging
import re
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import config, db

log = logging.getLogger('auth')
router = APIRouter(prefix='/api/auth', tags=['auth'])
COOKIE = 'gd_sesion'
HORAS_SESION = 10


def _secreto() -> str:
    if not config.JWT_SECRETO:
        if config.PRODUCCION:
            raise RuntimeError('Falta JWT_SECRETO')
        config.JWT_SECRETO = secrets.token_hex(32)
        log.warning('JWT_SECRETO vacío: se usa uno temporal (las sesiones se pierden al reiniciar)')
    return config.JWT_SECRETO


def _hash(email: str, codigo: str) -> str:
    return hmac.new(_secreto().encode(), f'{email}:{codigo}'.encode(), hashlib.sha256).hexdigest()


def enviar_correo(para: str, asunto: str, texto: str, html: str) -> None:
    if not config.SMTP_HOST:
        log.warning('[MODO DESARROLLO] Correo a %s | %s\n%s', para, asunto, texto)
        return
    m = EmailMessage()
    m['From'], m['To'], m['Subject'] = config.CORREO_REMITENTE, para, asunto
    m.set_content(texto)
    m.add_alternative(html, subtype='html')
    if config.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
            s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(m)
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(m)


def _correo_codigo(codigo: str) -> tuple[str, str]:
    texto = f'Tu código para entrar a Growvia Datos es {codigo}. Vence en 10 minutos. Si no lo pediste, ignora este correo.'
    html = f'''<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;color:#0f2a28">
      <h2 style="margin:0 0 12px;color:#013936">Growvia Datos</h2>
      <p>Tu código para entrar es:</p>
      <p style="font-size:32px;font-weight:700;letter-spacing:8px;margin:16px 0;color:#013936">{codigo}</p>
      <p style="color:#557">Vence en 10 minutos. Si no lo pediste, ignora este correo.</p></div>'''
    return texto, html


class PedirCodigo(BaseModel):
    email: str


class VerificarCodigo(BaseModel):
    email: str
    codigo: str


def _limpio(email: str) -> str:
    e = (email or '').strip().lower()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[a-z]{2,}', e):
        raise HTTPException(400, 'Escribe un correo válido')
    return e


@router.post('/codigo')
def pedir_codigo(dto: PedirCodigo):
    email = _limpio(dto.email)
    u = db.uno('SELECT id FROM usuarios WHERE email = %s AND activo', (email,))
    # La respuesta es la misma exista o no el correo (no se revela quién tiene acceso)
    respuesta = {'mensaje': 'Si tu correo tiene acceso, te llegó un código. Revisa también la carpeta de spam.'}
    if not u:
        db.registrar(None, 'INGRESO_SIN_ACCESO', {'email': email})
        return respuesta
    recientes = db.uno("SELECT count(*) AS n FROM codigos WHERE email = %s AND creado_at > now() - interval '1 hour'", (email,))
    if recientes['n'] >= 6:
        raise HTTPException(429, 'Pediste muchos códigos. Espera una hora e inténtalo de nuevo.')
    codigo = f'{secrets.randbelow(1_000_000):06d}'
    db.ejecutar("UPDATE codigos SET usado = true WHERE email = %s AND NOT usado", (email,))
    db.ejecutar("INSERT INTO codigos (email, codigo_hash, expira) VALUES (%s, %s, now() + interval '10 minutes')", (email, _hash(email, codigo)))
    texto, html = _correo_codigo(codigo)
    try:
        enviar_correo(email, f'{codigo} es tu código de Growvia Datos', texto, html)
    except Exception:
        log.exception('No se pudo enviar el código')
        raise HTTPException(502, 'No se pudo enviar el correo. Inténtalo en un momento.')
    return respuesta


@router.post('/verificar')
def verificar(dto: VerificarCodigo, response: Response):
    email = _limpio(dto.email)
    codigo = re.sub(r'\D', '', dto.codigo or '')
    c = db.uno('SELECT id, codigo_hash, intentos FROM codigos WHERE email = %s AND NOT usado AND expira > now() ORDER BY creado_at DESC LIMIT 1', (email,))
    if not c:
        raise HTTPException(400, 'El código venció o no existe. Pide uno nuevo.')
    if c['intentos'] >= 5:
        db.ejecutar('UPDATE codigos SET usado = true WHERE id = %s', (c['id'],))
        raise HTTPException(400, 'Demasiados intentos. Pide un código nuevo.')
    if not hmac.compare_digest(c['codigo_hash'], _hash(email, codigo)):
        db.ejecutar('UPDATE codigos SET intentos = intentos + 1 WHERE id = %s', (c['id'],))
        raise HTTPException(400, 'El código no es correcto')
    u = db.uno('SELECT id, email, nombre, rol FROM usuarios WHERE email = %s AND activo', (email,))
    if not u:
        raise HTTPException(403, 'Tu correo ya no tiene acceso')
    db.ejecutar('UPDATE codigos SET usado = true WHERE id = %s', (c['id'],))
    db.ejecutar('UPDATE usuarios SET ultimo_ingreso = now() WHERE id = %s', (u['id'],))
    db.registrar(u['id'], 'INGRESO')
    token = jwt.encode({'sub': str(u['id']), 'exp': datetime.now(timezone.utc) + timedelta(hours=HORAS_SESION)}, _secreto(), algorithm='HS256')
    response.set_cookie(COOKIE, token, httponly=True, secure=config.PRODUCCION, samesite='strict', max_age=HORAS_SESION * 3600, path='/')
    return {'usuario': u}


@router.post('/salir')
def salir(response: Response):
    response.delete_cookie(COOKIE, path='/')
    return {'ok': True}


def usuario_actual(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, 'Inicia sesión')
    try:
        datos = jwt.decode(token, _secreto(), algorithms=['HS256'])
    except jwt.PyJWTError:
        raise HTTPException(401, 'Tu sesión venció. Vuelve a entrar.')
    u = db.uno('SELECT id, email, nombre, rol FROM usuarios WHERE id = %s AND activo', (int(datos['sub']),))
    if not u:
        raise HTTPException(401, 'Tu correo ya no tiene acceso')
    return u


def solo_admin(u: dict = Depends(usuario_actual)) -> dict:
    if u['rol'] != 'ADMIN':
        raise HTTPException(403, 'Solo un administrador puede hacer esto')
    return u


@router.get('/yo')
def yo(u: dict = Depends(usuario_actual)):
    return u
