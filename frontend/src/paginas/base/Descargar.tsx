import { useMemo, useState } from 'react';
import type { Trabajo } from '../../api';

const CONFIABLES = ['DEL_ARCHIVO', 'EXACTO', 'ELEGIDO', 'COINCIDENCIA'];
const SEGMENTOS: Record<string, string> = {
  todos: 'Todas', micro: 'Solo micro', pyme: 'Solo pymes (pequeña y mediana)', grande: 'Solo grandes', sin: 'Sin segmento',
};

export function Descargar({ trabajo, onDescargado }: { trabajo: Trabajo; onDescargado: () => void }) {
  const [segmento, setSegmento] = useState('todos');
  const [soloListas, setSoloListas] = useState(true);
  const [inactivas, setInactivas] = useState(false);

  const filas = useMemo(() => trabajo.filas.filter((f) => {
    if (f.rucEstado === 'DESCARTADA') return false;
    if (soloListas && !CONFIABLES.includes(f.rucEstado)) return false;
    if (!inactivas && !f.final.activo) return false;
    const s = f.final.segmento;
    if (segmento === 'micro') return s === 'Micro';
    if (segmento === 'pyme') return s === 'Pequeña' || s === 'Mediana';
    if (segmento === 'grande') return s === 'Grande';
    if (segmento === 'sin') return !s;
    return true;
  }), [trabajo.filas, segmento, soloListas, inactivas]);
  const incompletas = filas.filter((f) => f.faltan.length).length;
  const url = `/api/trabajos/${trabajo.id}/excel?${new URLSearchParams({ segmento, solo_listas: String(soloListas), incluir_inactivas: String(inactivas) })}`;

  return (
    <div style={{ display: 'grid', gap: 18, gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p className="suave">
          El Excel sale con las 11 columnas de la plantilla del CRM (RUC, razón social, representante, DNI, teléfono, correo, ubicación, líneas y operador),
          seguidas de columnas de control y las columnas originales del archivo. Súbelo en el CRM con <b>Cargar base</b>: no se duplican empresas.
        </p>
        <div className="campo" style={{ maxWidth: 320 }}>
          <label className="etiqueta" htmlFor="seg-descarga">Empresas</label>
          <select id="seg-descarga" className="selector" value={segmento} onChange={(e) => setSegmento(e.target.value)}>
            {Object.entries(SEGMENTOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <label className="casilla"><input type="checkbox" checked={soloListas} onChange={(e) => setSoloListas(e.target.checked)} />Solo con RUC confirmado (sin las probables sin revisar)</label>
        <label className="casilla"><input type="checkbox" checked={inactivas} onChange={(e) => setInactivas(e.target.checked)} />Incluir empresas de baja o suspendidas</label>
      </div>
      <div className="tarjeta tarjeta--plana" style={{ background: '#fbfcfa' }}>
        <div><div className="cifra numeros">{filas.length}</div><span className="suave">empresas en el Excel</span></div>
        {incompletas > 0 && <div className="nota nota--ambar">{incompletas} todavía tienen algún dato vacío. El CRM las acepta y la asesora lo completa después.</div>}
        <a className="boton" href={filas.length ? url : undefined} aria-disabled={!filas.length} onClick={() => filas.length && onDescargado()}
          style={filas.length ? undefined : { pointerEvents: 'none', background: '#9fb3ae' }} download>
          Descargar Excel para el CRM
        </a>
      </div>
    </div>
  );
}
