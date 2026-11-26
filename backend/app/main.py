"""Growvia Datos: completar bases de empresas antes de subirlas al CRM."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, config, db, trabajos, usuarios

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')


@asynccontextmanager
async def vida(_: FastAPI):
    db.iniciar()
    trabajos.reanudar()
    yield
    db.cerrar()


app = FastAPI(title='Growvia Datos', lifespan=vida, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(trabajos.router)


@app.middleware('http')
async def cabeceras(request: Request, call_next):
    r = await call_next(request)
    r.headers['X-Content-Type-Options'] = 'nosniff'
    r.headers['X-Frame-Options'] = 'DENY'
    r.headers['Referrer-Policy'] = 'same-origin'
    if request.url.path.startswith('/api/'):
        r.headers['Cache-Control'] = 'no-store'
    return r


@app.get('/api/salud')
def salud():
    db.uno('SELECT 1')
    return {'ok': True}


@app.exception_handler(Exception)
async def error_general(_: Request, e: Exception):
    logging.getLogger('app').exception('Error no controlado')
    return JSONResponse({'detail': 'Ocurrió un error inesperado. Inténtalo de nuevo.'}, status_code=500)


# Frontend (React compilado): cualquier ruta que no sea /api devuelve index.html
_dist = os.path.abspath(config.CARPETA_FRONTEND)
if os.path.isdir(_dist):
    app.mount('/assets', StaticFiles(directory=os.path.join(_dist, 'assets')), name='assets')

    @app.get('/{ruta:path}', include_in_schema=False)
    def spa(ruta: str):
        archivo = os.path.join(_dist, ruta)
        if ruta and not ruta.startswith('api/') and os.path.isfile(archivo) and os.path.commonpath([_dist, os.path.abspath(archivo)]) == _dist:
            return FileResponse(archivo)
        if ruta.startswith('api/'):
            return JSONResponse({'detail': 'No existe'}, status_code=404)
        return FileResponse(os.path.join(_dist, 'index.html'), headers={'Cache-Control': 'no-cache'})
