import type { EstadoRuc, EstadoTrabajo } from '../api';

const ESTADOS: Record<EstadoTrabajo, [string, string]> = {
  CARGADO: ['Cargada', 'chip--gris'],
  BUSCANDO_RUC: ['Buscando RUC', 'chip'],
  REVISAR_RUC: ['Revisar RUC', 'chip--ambar'],
  CONSULTANDO: ['Consultando SUNAT', 'chip'],
  REVISION: ['En revisión', 'chip--ok'],
  ERROR: ['Error', 'chip--alerta'],
};

export function ChipEstado({ estado }: { estado: EstadoTrabajo }) {
  const [texto, clase] = ESTADOS[estado] ?? [estado, 'chip--gris'];
  return <span className={`chip ${clase}`}>{texto}</span>;
}

const RUC: Record<EstadoRuc, [string, string]> = {
  DEL_ARCHIVO: ['Del archivo', 'chip--ok'],
  EXACTO: ['Exacto', 'chip--ok'],
  ELEGIDO: ['Elegido', 'chip--ok'],
  COINCIDENCIA: ['Coincidencia', 'chip--ok'],
  PROBABLE: ['Probable', 'chip--ambar'],
  VARIOS: ['Varios posibles', 'chip--ambar'],
  NO_ENCONTRADO: ['No encontrado', 'chip--alerta'],
  INVALIDO: ['RUC no válido', 'chip--alerta'],
  DESCARTADA: ['Descartada', 'chip--gris'],
};

export function ChipRuc({ estado }: { estado: EstadoRuc }) {
  const [texto, clase] = RUC[estado] ?? [estado, 'chip--gris'];
  return <span className={`chip ${clase}`}>{texto}</span>;
}
