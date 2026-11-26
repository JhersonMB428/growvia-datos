"""Leer la base que llega y armar el Excel con la plantilla del CRM."""
import io
from datetime import date, datetime

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .normalizar import normal, solo_digitos

OPERADORES = ['Movistar', 'Claro', 'Entel', 'Bitel']

# Columnas que se reconocen en la base que llega (el resto se conserva tal cual)
ALIAS = {
    'ruc': ['RUC', 'NRO RUC', 'NUMERO DE RUC', 'N RUC'],
    'razon': ['RAZON SOCIAL', 'CLIENTE FINAL', 'CLIENTE', 'EMPRESA', 'NOMBRE', 'NOMBRE O RAZON SOCIAL'],
    'contacto': ['REPRESENTANTEL LEGAL SUNAT', 'REPRESENTANTE LEGAL SUNAT', 'REPRESENTANTE LEGAL', 'REPRESENTANTE', 'CONTACTO PRESUNTO', 'CONTACTO'],
    'dni': ['DNI', 'DNI REPRESENTANTE', 'DOCUMENTO'],
    'telefono': ['TELEFONO', 'CELULAR', 'TELEFONO CONTACTO', 'MOVIL'],
    'correo': ['CORREO', 'EMAIL', 'E MAIL', 'CORREO ELECTRONICO'],
    'departamento': ['DEPARTAMENTO'], 'provincia': ['PROVINCIA'], 'distrito': ['DISTRITO'],
    'lineas': ['CANTIDAD DE LINEAS', 'LINEAS', 'NRO LINEAS', 'TOTAL LINEAS'],
    'operador': ['OPERADOR', 'OPERADOR ACTUAL'],
    'lineas_movistar': ['LINEAS MOVISTAR', 'MOVISTAR'], 'lineas_claro': ['LINEAS CLARO', 'CLARO'],
    'lineas_entel': ['LINEAS ENTEL', 'ENTEL'], 'lineas_bitel': ['LINEAS BITEL', 'BITEL'],
    'segmento': ['SEGMENTO', 'TAMANO', 'TIPO DE EMPRESA'],
}


class ErrorArchivo(Exception):
    pass


def _valor(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10]
    return str(v).strip()


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """Filas reconocidas y nombres de las columnas extra"""
    try:
        libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception:
        raise ErrorArchivo('No se pudo abrir el archivo. Súbelo como Excel (.xlsx).')
    hoja = libro.worksheets[0]
    filas = [list(f) for f in hoja.iter_rows(values_only=True)]
    libro.close()
    # El encabezado es la primera fila (de las 10 primeras) donde se reconoce RUC o razón social
    conocidos = {a for v in ALIAS.values() for a in v}
    inicio = next((i for i, f in enumerate(filas[:10]) if {'RUC', 'RAZON SOCIAL', 'CLIENTE FINAL', 'CLIENTE', 'EMPRESA'} & {normal(x) for x in f}), None)
    if inicio is None:
        raise ErrorArchivo('No encontré la columna RUC ni RAZÓN SOCIAL / CLIENTE FINAL en las primeras filas.')
    enc = [normal(x) for x in filas[inicio]]
    mapa: dict[str, int] = {}
    for campo, alias in ALIAS.items():
        for a in alias:
            if a in enc and enc.index(a) not in mapa.values():
                mapa[campo] = enc.index(a)
                break
    extras = [(i, _valor(filas[inicio][i])) for i in range(len(enc)) if i not in mapa.values() and _valor(filas[inicio][i]) and enc[i] not in conocidos]
    salida = []
    for n, f in enumerate(filas[inicio + 1:], start=inicio + 2):
        if not any(_valor(x) for x in f):
            continue
        dato = {c: _valor(f[i]) if i < len(f) else '' for c, i in mapa.items()}
        dato['ruc'] = solo_digitos(dato.get('ruc'))
        salida.append({'n': n, 'original': dato, 'extra': {nombre: _valor(f[i]) if i < len(f) else '' for i, nombre in extras}})
    if not salida:
        raise ErrorArchivo('El archivo no tiene filas con datos.')
    if len(salida) > 20000:
        raise ErrorArchivo('El archivo tiene más de 20 000 filas. Divídelo en partes.')
    return salida, [x[1] for x in extras]


COLUMNAS_CRM = ['RUC', 'RAZÓN SOCIAL', 'REPRESENTANTEL LEGAL SUNAT', 'DNI', 'TELEFONO', 'CORREO',
                'DEPARTAMENTO', 'PROVINCIA', 'DISTRITO', 'CANTIDAD DE LÍNEAS', 'OPERADOR']
CONTROL = ['SEGMENTO', 'TRABAJADORES', 'PERIODO TRABAJADORES'] + [f'LÍNEAS {o.upper()}' for o in OPERADORES] + \
          ['ESTADO SUNAT', 'CARGO DEL REPRESENTANTE', 'OTROS TELÉFONOS', 'OTROS CORREOS', 'DIRECCIÓN',
           'NOMBRE EN EL ARCHIVO', 'CÓMO SE ENCONTRÓ EL RUC', 'OBSERVACIÓN']


def generar(filas: list[dict], extras: list[str]) -> bytes:
    """filas: lo que devuelve trabajos.final(); cada una con las claves de COLUMNAS_CRM y CONTROL"""
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = 'Base CRM'
    hoja.append(COLUMNAS_CRM + CONTROL + [x.upper() for x in extras])
    for f in filas:
        hoja.append([f['ruc'], f['razon'], f['representante'], f['dni'], f['telefono'], f['correo'],
                     f['departamento'], f['provincia'], f['distrito'], f['lineas'] if f['lineas'] is not None else '', f['operador'],
                     f['segmento'], f['trabajadores'] if f['trabajadores'] is not None else '', f['periodo'],
                     *[f['lineas_por'].get(o.lower()) if f['lineas_por'].get(o.lower()) is not None else '' for o in OPERADORES],
                     f['estado_sunat'], f['cargo'], ', '.join(f['otros_telefonos']), ', '.join(f['otros_correos']), f['direccion'],
                     f['nombre_archivo'], f['como_ruc'], f['observacion']]
                    + [f['extra'].get(x, '') for x in extras])
    verde, gris = PatternFill('solid', fgColor='013936'), PatternFill('solid', fgColor='5B6B69')
    for i, celda in enumerate(hoja[1]):
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = verde if i < len(COLUMNAS_CRM) else gris
        celda.alignment = Alignment(wrap_text=True, vertical='center')
    hoja.row_dimensions[1].height = 32
    anchos = [13, 42, 34, 11, 12, 30, 14, 16, 20, 11, 11, 11, 12, 12, 10, 10, 10, 10, 18, 24, 24, 28, 44, 40, 22, 30]
    for i, ancho in enumerate(anchos + [18] * len(extras), start=1):
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    for fila in hoja.iter_rows(min_row=2):
        for c in (fila[0], fila[3], fila[4]):
            c.number_format = '@'
    hoja.freeze_panes = 'C2'
    hoja.auto_filter.ref = hoja.dimensions
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
