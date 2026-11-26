"""Pruebas rápidas sin base de datos:  python -m pytest -q"""
import io
import zipfile

import openpyxl

from app import apiconsulta, excel, padron
from app.normalizar import normal, ruc_valido, telefono


def test_ruc():
    assert ruc_valido('20100047218')
    assert not ruc_valido('20100047219')
    assert not ruc_valido('3010004721')


def test_normal():
    assert normal("PARDO'S CHICKEN S.A.C.") == normal('PARDOS CHICKEN SOCIEDAD ANONIMA CERRADA') == 'PARDOS CHICKEN SAC'


def test_telefono():
    assert telefono('+51 987 654 321') == '987654321'
    assert telefono('01-4567890') == '014567890'
    assert telefono('12') == ''


def _padron(lineas):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('padron_reducido_ruc.txt', '\n'.join(['RUC|NOMBRE|ESTADO|CONDICION|UBIGEO|A|B|C|D|E|F|G|H|I|J|'] + lineas).encode('latin-1'))
    return b


def test_escanear_y_elegir(tmp_path):
    ruta = tmp_path / 'p.zip'
    ruta.write_bytes(_padron([
        '20600000005|HILANDERIA DE ALGODON PERUANO S.A.|ACTIVO|HABIDO|150122|AV.|LARCO|-|-|123|-|-|-|-|-|',
        '20600000013|PARDOS CHICKEN SOCIEDAD ANONIMA CERRADA|ACTIVO|HABIDO|150101|-|-|-|-|-|-|-|-|-|-|',
        '20600000021|TRANSPORTES ANDINOS DEL SUR SAC|ACTIVO|HABIDO|150101|-|-|-|-|-|-|-|-|-|-|',
        '20100047218|BANCO DE PRUEBA|ACTIVO|HABIDO|150101|-|-|-|-|-|-|-|-|-|-|',
    ]).getvalue())
    por_ruc, cands = padron.escanear(str(ruta), {'20100047218'}, {1: 'Hilandería de Algodón Peruano SA', 2: "PARDO'S CHICKEN S.A.C.", 3: 'Transportes Andinos', 4: 'No existe SAC'})
    assert por_ruc['20100047218']['razon'] == 'BANCO DE PRUEBA'
    assert padron.elegir(cands[1])[:2] == ('20600000005', 'EXACTO')
    assert padron.elegir(cands[2])[:2] == ('20600000013', 'EXACTO')
    assert padron.elegir(cands[3])[:2] == ('20600000021', 'PROBABLE')
    assert padron.elegir(cands.get(4, []))[1] == 'NO_ENCONTRADO'
    assert 'LARCO' in cands[1][0]['direccion']


def test_resumenes():
    reps = apiconsulta.representantes([{'nombre': 'ROJAS ANA', 'cargo': 'APODERADO', 'numero_de_documento': 41234567, 'tipo_de_documento': 'DNI'},
                                       {'nombre': 'PEREZ LUIS', 'cargo': 'GERENTE GENERAL', 'numero_de_documento': '10234567', 'tipo_de_documento': 'DOC. NACIONAL DE IDENTIDAD'}])
    assert reps[0]['nombre'] == 'Perez Luis' and reps[0]['dni'] == '10234567'
    assert apiconsulta.contacto({'telefonos': ['987654321', '987654321'], 'correos': ['A@B.PE']}) == {'telefonos': ['987654321'], 'correos': ['a@b.pe']}
    assert apiconsulta.trabajadores([{'periodo': '2026-08', 'trabajadores': 5}, {'periodo': '2026-09', 'trabajadores': '12'}])['trabajadores'] == 12
    assert [apiconsulta.tamano(n) for n in (3, 50, 200, 900)] == ['Micro', 'Pequeña', 'Mediana', 'Grande']


def test_leer_excel():
    libro = openpyxl.Workbook()
    h = libro.active
    h.append(['Reporte de clientes'])
    h.append(['CLIENTE FINAL', 'CONTACTO (PRESUNTO)', 'Movistar', 'Sector'])
    h.append(['ACME SAC', 'Juan', 5, 'Retail'])
    b = io.BytesIO()
    libro.save(b)
    filas, extras = excel.leer(b.getvalue())
    assert filas[0]['original']['razon'] == 'ACME SAC' and filas[0]['original']['lineas_movistar'] == '5'
    assert extras == ['Sector'] and filas[0]['n'] == 3
