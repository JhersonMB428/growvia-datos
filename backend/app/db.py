"""Conexión a PostgreSQL (psycopg 3 con pool)."""
import json
import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None


def iniciar() -> None:
    global _pool
    _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=8, kwargs={'row_factory': dict_row}, open=True)
    with open(os.path.join(os.path.dirname(__file__), 'esquema.sql'), encoding='utf-8') as f:
        sql = f.read()
    with conexion() as c:
        c.execute(sql)
        for email in config.ADMIN_INICIAL:
            c.execute(
                "INSERT INTO usuarios (email, rol, activo) VALUES (%s, 'ADMIN', true) "
                "ON CONFLICT (email) DO UPDATE SET rol = 'ADMIN', activo = true", (email,))


def cerrar() -> None:
    if _pool:
        _pool.close()


@contextmanager
def conexion():
    assert _pool, 'La base de datos no está iniciada'
    with _pool.connection() as c:
        yield c


def uno(sql: str, params=()) -> dict | None:
    with conexion() as c:
        return c.execute(sql, params).fetchone()


def todos(sql: str, params=()) -> list[dict]:
    with conexion() as c:
        return c.execute(sql, params).fetchall()


def ejecutar(sql: str, params=()) -> None:
    with conexion() as c:
        c.execute(sql, params)


def j(valor) -> Jsonb:
    """Valor para una columna jsonb"""
    return Jsonb(valor)


def registrar(usuario_id: int | None, accion: str, detalle: dict | None = None) -> None:
    ejecutar('INSERT INTO actividad (usuario_id, accion, detalle) VALUES (%s, %s, %s)',
             (usuario_id, accion, j(detalle) if detalle else None))


def ajuste(clave: str, defecto=None):
    f = uno('SELECT valor FROM ajustes WHERE clave = %s', (clave,))
    return f['valor'] if f else defecto


def guardar_ajuste(clave: str, valor) -> None:
    ejecutar('INSERT INTO ajustes (clave, valor) VALUES (%s, %s) ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado_at = now()',
             (clave, j(valor)))


__all__ = ['iniciar', 'cerrar', 'conexion', 'uno', 'todos', 'ejecutar', 'j', 'registrar', 'ajuste', 'guardar_ajuste', 'json']
