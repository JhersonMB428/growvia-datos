"""
Simula apiconsulta.dev para probar sin gastar consultas.
  uvicorn tests.mock_apiconsulta:app --port 4010
y en .env: APICONSULTA_URL=http://localhost:4010  APICONSULTA_TOKEN=prueba-local
"""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI()
LLAMADAS = {'n': 0}


class Cuerpo(BaseModel):
    ruc: str


def _token(authorization: str | None):
    LLAMADAS['n'] += 1
    if authorization != 'Bearer prueba-local':
        raise HTTPException(401, 'token')


@app.post('/ruc')
def ruc(c: Cuerpo, authorization: str | None = Header(None)):
    _token(authorization)
    return {'success': True, 'data': {'ruc': int(c.ruc), 'nombre_o_razon_social': f'EMPRESA MANUAL {c.ruc[-4:]} SAC', 'estado': 'ACTIVO',
                                      'condicion': 'HABIDO', 'direccion': 'AV. AREQUIPA 123', 'ubigeo': {'ubigeo': 150122, 'distrito': 'MIRAFLORES'}}}


@app.post('/ruc-representantes')
def representantes(c: Cuerpo, authorization: str | None = Header(None)):
    _token(authorization)
    r = c.ruc
    return {'success': True, 'data': [
        {'tipo_de_documento': 'DNI', 'numero_de_documento': '4' + r[3:10], 'nombre': f'PEREZ ROJAS JUAN {r[-3:]}', 'cargo': 'GERENTE GENERAL', 'fecha_desde': '2020-01-01'},
        {'tipo_de_documento': 'DNI', 'numero_de_documento': '7' + r[4:11], 'nombre': f'QUISPE MAMANI ROSA {r[-2:]}', 'cargo': 'APODERADO', 'fecha_desde': '2022-05-10'},
    ]}


@app.post('/ruc-contacto')
def contacto(c: Cuerpo, authorization: str | None = Header(None)):
    _token(authorization)
    if c.ruc.endswith('7'):
        return {'success': True, 'data': {'telefonos': [], 'correos': []}}
    return {'success': True, 'data': {'telefonos': ['01-4567890', '+51 987 654 ' + c.ruc[-3:]], 'correos': [f'Ventas{c.ruc[-3:]}@Empresa.pe', 'no-es-correo']}}


@app.post('/ruc-trabajadores')
def trabajadores(c: Cuerpo, authorization: str | None = Header(None)):
    _token(authorization)
    n = int(c.ruc[-3:]) % 400
    return {'success': True, 'data': [
        {'periodo': '2026-08', 'trabajadores': n, 'pensionistas': 0, 'prestadores_servicio': 2},
        {'periodo': '2026-09', 'trabajadores': n + 1, 'pensionistas': 0, 'prestadores_servicio': 3},
    ]}


@app.get('/llamadas')
def llamadas():
    return LLAMADAS
