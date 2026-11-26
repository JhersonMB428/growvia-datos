import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, fecha, textoError, type TrabajoResumen } from '../api';
import { ChipEstado } from './comunes';

export function Bases() {
  const navegar = useNavigate();
  const [bases, setBases] = useState<TrabajoResumen[] | null>(null);
  const [error, setError] = useState('');
  const [subiendo, setSubiendo] = useState(false);
  const [encima, setEncima] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const cargar = useCallback(() => api<TrabajoResumen[]>('/trabajos').then(setBases).catch((e) => setError(textoError(e))), []);
  useEffect(() => { cargar(); }, [cargar]);

  async function subir(archivo: File | undefined) {
    if (!archivo) return;
    setError(''); setSubiendo(true);
    const f = new FormData();
    f.append('archivo', archivo);
    try {
      const r = await api<{ id: string }>('/trabajos', { formulario: f });
      navegar(`/bases/${r.id}`);
    } catch (e) { setError(textoError(e)); setSubiendo(false); }
    if (input.current) input.current.value = '';
  }

  return (
    <>
      <div className="encabezado">
        <div>
          <h1>Bases</h1>
          <p>Sube una base de empresas, completa sus datos con SUNAT y descárgala lista para <b>Cargar base</b> en el CRM.</p>
        </div>
      </div>

      <div
        className={`zona-subir${encima ? ' zona-subir--encima' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setEncima(true); }}
        onDragLeave={() => setEncima(false)}
        onDrop={(e) => { e.preventDefault(); setEncima(false); subir(e.dataTransfer.files[0]); }}
      >
        <div style={{ flex: 1, minWidth: 260 }}>
          <h2>Subir una base nueva</h2>
          <p className="suave" style={{ marginTop: 4, fontSize: 14 }}>
            Excel (.xlsx) con una columna <b>RUC</b> o <b>Razón social / Cliente final</b>. Las demás columnas se conservan.
            Buscar el RUC en el padrón de SUNAT es gratis; solo la consulta de representante, contacto y trabajadores gasta del plan.
          </p>
        </div>
        <input ref={input} type="file" accept=".xlsx,.xlsm" hidden onChange={(e) => subir(e.target.files?.[0])} />
        <button type="button" className="boton" disabled={subiendo} onClick={() => input.current?.click()}>{subiendo ? 'Subiendo…' : 'Elegir archivo'}</button>
      </div>
      {error && <div className="alerta" role="alert">{error}</div>}

      <div className="tarjeta">
        <h2>Bases subidas</h2>
        {bases === null ? <p className="tenue">Cargando…</p> : bases.length === 0 ? (
          <p className="tenue">Todavía no hay bases. Sube la primera arriba.</p>
        ) : (
          <div className="tabla-caja">
            <table className="tabla">
              <thead>
                <tr><th>Base</th><th>Estado</th><th className="celda-num">Empresas</th><th className="celda-num">Con RUC</th><th className="celda-num">Por revisar</th><th className="celda-num">Consultadas</th><th>Subida por</th><th>Fecha</th></tr>
              </thead>
              <tbody>
                {bases.map((b) => (
                  <tr key={b.id} className="fila--clic" onClick={() => navegar(`/bases/${b.id}`)}>
                    <td><a href={`/bases/${b.id}`} onClick={(e) => { e.preventDefault(); navegar(`/bases/${b.id}`); }}>{b.nombre}</a></td>
                    <td><ChipEstado estado={b.estado} /></td>
                    <td className="celda-num numeros">{b.filas}</td>
                    <td className="celda-num numeros">{b.conRuc}</td>
                    <td className="celda-num numeros">{b.porRevisar || '—'}</td>
                    <td className="celda-num numeros">{b.consultadas || '—'}</td>
                    <td>{b.creadoPor}</td>
                    <td className="numeros">{fecha(b.creadoAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
