"""Apartado de Accesos: el administrador decide qué correos pueden entrar."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db
from .auth import solo_admin

router = APIRouter(prefix='/api/usuarios', tags=['usuarios'])


class NuevoUsuario(BaseModel):
    email: str
    nombre: str = ''
    rol: str = 'USUARIO'


class CambioUsuario(BaseModel):
    nombre: str | None = None
    rol: str | None = None
    activo: bool | None = None


@router.get('')
def listar(_: dict = Depends(solo_admin)):
    return db.todos('''SELECT u.id, u.email, u.nombre, u.rol, u.activo, u.creado_at AS "creadoAt", u.ultimo_ingreso AS "ultimoIngreso",
                              c.email AS "creadoPor"
                       FROM usuarios u LEFT JOIN usuarios c ON c.id = u.creado_por ORDER BY u.activo DESC, u.email''')


@router.post('')
def crear(dto: NuevoUsuario, admin: dict = Depends(solo_admin)):
    email = dto.email.strip().lower()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[a-z]{2,}', email):
        raise HTTPException(400, 'Escribe un correo válido')
    if dto.rol not in ('ADMIN', 'USUARIO'):
        raise HTTPException(400, 'Rol no válido')
    if db.uno('SELECT 1 FROM usuarios WHERE email = %s', (email,)):
        raise HTTPException(400, 'Ese correo ya está en la lista. Actívalo desde aquí si estaba desactivado.')
    u = db.uno('INSERT INTO usuarios (email, nombre, rol, creado_por) VALUES (%s, %s, %s, %s) RETURNING id',
               (email, dto.nombre.strip()[:80], dto.rol, admin['id']))
    db.registrar(admin['id'], 'ACCESO_DADO', {'email': email, 'rol': dto.rol})
    return {'id': u['id']}


@router.patch('/{uid}')
def cambiar(uid: int, dto: CambioUsuario, admin: dict = Depends(solo_admin)):
    u = db.uno('SELECT id, email, rol, activo FROM usuarios WHERE id = %s', (uid,))
    if not u:
        raise HTTPException(404, 'El usuario no existe')
    if dto.rol is not None and dto.rol not in ('ADMIN', 'USUARIO'):
        raise HTTPException(400, 'Rol no válido')
    quita_admin = u['rol'] == 'ADMIN' and ((dto.rol and dto.rol != 'ADMIN') or dto.activo is False)
    if quita_admin:
        if uid == admin['id']:
            raise HTTPException(400, 'No puedes quitarte el acceso de administrador a ti mismo')
        otros = db.uno("SELECT count(*) AS n FROM usuarios WHERE rol = 'ADMIN' AND activo AND id <> %s", (uid,))
        if otros['n'] == 0:
            raise HTTPException(400, 'Debe quedar al menos un administrador activo')
    db.ejecutar('UPDATE usuarios SET nombre = COALESCE(%s, nombre), rol = COALESCE(%s, rol), activo = COALESCE(%s, activo) WHERE id = %s',
                (dto.nombre.strip()[:80] if dto.nombre is not None else None, dto.rol, dto.activo, uid))
    db.registrar(admin['id'], 'ACCESO_CAMBIADO', {'email': u['email'], **dto.model_dump(exclude_none=True)})
    return {'ok': True}


@router.get('/actividad')
def actividad(_: dict = Depends(solo_admin)):
    return db.todos('''SELECT a.id, a.accion, a.detalle, a.creado_at AS "fecha", u.email
                       FROM actividad a LEFT JOIN usuarios u ON u.id = a.usuario_id ORDER BY a.id DESC LIMIT 200''')
