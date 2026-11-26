"""Normalizar razones sociales y validar RUC."""
import re
import unicodedata

PESOS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

FORMAS = [
    (r'\bSOCIEDAD ANONIMA CERRADA\b', 'SAC'), (r'\bSOCIEDAD ANONIMA ABIERTA\b', 'SAA'), (r'\bSOCIEDAD ANONIMA\b', 'SA'),
    (r'\bSOCIEDAD COMERCIAL DE RESPONSABILIDAD LIMITADA\b', 'SRL'), (r'\bEMPRESA INDIVIDUAL DE RESPONSABILIDAD LIMITADA\b', 'EIRL'),
    (r'\bS\s*A\s*C\b', 'SAC'), (r'\bS\s*A\s*A\b', 'SAA'), (r'\bS\s*R\s*L\b', 'SRL'), (r'\bE\s*I\s*R\s*L\b', 'EIRL'), (r'\bS\s*A\b', 'SA'),
    (r'\bS CIVIL DE R L\b', 'SCRL'), (r'\bSOCIEDAD CIVIL DE RESPONSABILIDAD LIMITADA\b', 'SCRL'),
]
FORMAS_RE = [(re.compile(p), c) for p, c in FORMAS]
COMUNES = {'SAC', 'SA', 'SAA', 'SRL', 'EIRL', 'SCRL', 'DE', 'DEL', 'LA', 'LAS', 'LOS', 'EL', 'Y', 'E', 'EN', 'PERU', 'SEDE'}

# Tabla rápida (en C) para separar palabras al recorrer los millones de filas del padrón
_TABLA = {}
for _i in range(256):
    _c = chr(_i)
    _b = unicodedata.normalize('NFD', _c).encode('ascii', 'ignore').decode().upper()
    if len(_b) == 1 and _b.isalnum():
        _TABLA[_i] = _b
    elif _c in ".'´`":
        _TABLA[_i] = ''
    else:
        _TABLA[_i] = ' '
_TABLA[ord('&')] = ' Y '


def palabras_rapidas(texto: str) -> set[str]:
    """Palabras en mayúsculas sin tildes ni signos (sin unir formas societarias). Solo para filtrar."""
    return set(texto.translate(_TABLA).split())


def normal(texto) -> str:
    t = unicodedata.normalize('NFD', str(texto or '')).encode('ascii', 'ignore').decode().upper()
    t = t.replace('&', ' Y ').replace('.', '').replace("'", '').replace('´', '').replace('`', '')
    t = re.sub(r'[^A-Z0-9 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    for patron, cambio in FORMAS_RE:
        t = patron.sub(cambio, t)
    return re.sub(r'\s+', ' ', t).strip()


def claves(nombre) -> set[str]:
    """Palabras que identifican a la empresa (sin forma societaria ni artículos)"""
    return {p for p in normal(nombre).split() if p not in COMUNES and len(p) > 1}


def ruc_valido(ruc: str) -> bool:
    if not re.fullmatch(r'(10|15|16|17|20)\d{9}', ruc or ''):
        return False
    resto = 11 - sum(p * int(d) for p, d in zip(PESOS, ruc)) % 11
    return {10: 0, 11: 1}.get(resto, resto) == int(ruc[10])


def solo_digitos(v) -> str:
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r'\D', '', str(v or ''))


def texto(v) -> str:
    return '' if v is None or isinstance(v, (dict, list)) else re.sub(r'\s+', ' ', str(v)).strip()


def nombre_propio(t: str) -> str:
    return re.sub(r"(^|[\s'-])(\w)", lambda m: m.group(1) + m.group(2).upper(), (t or '').lower())


def telefono(v) -> str:
    """Celular de 9 dígitos (9XXXXXXXX) o fijo; vacío si no parece teléfono"""
    d = solo_digitos(v)
    if d.startswith('51') and len(d) == 11:
        d = d[2:]
    if len(d) == 9 and d[0] == '9':
        return d
    if 6 <= len(d) <= 9:
        return d
    return ''
