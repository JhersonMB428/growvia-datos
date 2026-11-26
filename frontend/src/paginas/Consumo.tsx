import { useEffect, useState } from 'react';
import { api, fecha, textoError, type Consumo as TipoConsumo } from '../api';
import { useSesion } from '../sesion';

const NOMBRES: Record<string, string> = { representantes: 'Representante legal', contacto: 'Teléfonos y correos', trabajadores: 'Trabajadores' };

export function Consumo() {
  const { usuario } = useSesion();
  const [c, setC] = useState<TipoConsumo | null>(null);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  useEffect(() => { api<TipoConsumo>('/consumo').then(setC).catch((e) => setError(textoError(e))); }, []);

  async function actualizarPadron() {
    if (!confirm('¿Descargar de nuevo el padrón de SUNAT? Tarda unos minutos; mientras, las búsquedas de RUC esperan.')) return;
    try { const r = await api<{ mensaje: string }>('/padron/actualizar', { metodo: 'POST' }); setAviso(r.mensaje); }
    catch (e) { setError(textoError(e)); }
  }

  if (!c) return error ? <div className="alerta">{error}</div> : <p className="tenue">Cargando…</p>;
  const porcentaje = Math.min(100, (c.usadasMes / Math.max(1, c.limiteMes)) * 100);
  const maximo = Math.max(1, ...c.porDia.map((d) => d.pagadas));

  return (
    <>
      <div className="encabezado">
        <div>
          <h1>Consumo de apiconsulta</h1>
          <p>Cada dato que se trae de SUNAT (representante, contacto o trabajadores) es una consulta del plan. Lo ya consultado en los últimos 60 días se reutiliza gratis.</p>
        </div>
      </div>
      {!c.tokenActivo && <div className="nota nota--ambar">El token de apiconsulta no está configurado: se puede buscar RUC en el padrón, pero no consultar SUNAT.</div>}
      <div className="rejilla" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
        <div className="tarjeta">
          <span className="etiqueta">Este mes</span>
          <div className="cifra numeros">{c.usadasMes.toLocaleString('es-PE')} <span style={{ fontSize: 16 }} className="tenue">de {c.limiteMes.toLocaleString('es-PE')}</span></div>
          <div className={`medidor${porcentaje >= 90 ? ' medidor--alto' : ''}`}><span style={{ width: `${porcentaje}%` }} /></div>
          <span className="suave" style={{ fontSize: 13 }}>Quedan {Math.max(0, c.limiteMes - c.usadasMes).toLocaleString('es-PE')} consultas. El plan se renueva cada mes.</span>
        </div>
        <div className="tarjeta">
          <span className="etiqueta">Por tipo de dato (este mes)</span>
          {c.porEndpoint.length ? c.porEndpoint.map((e) => (
            <div key={e.endpoint} className="fila fila--entre"><span>{NOMBRES[e.endpoint] ?? e.endpoint}</span><b className="numeros">{e.pagadas}</b></div>
          )) : <p className="tenue">Sin consultas este mes.</p>}
        </div>
        <div className="tarjeta">
          <span className="etiqueta">Por persona (este mes)</span>
          {c.porUsuario.length ? c.porUsuario.map((u) => (
            <div key={u.email ?? '—'} className="fila fila--entre"><span>{u.email ?? '—'}</span><span className="numeros"><b>{u.pagadas}</b> <span className="tenue">+ {u.reutilizadas} reutilizadas</span></span></div>
          )) : <p className="tenue">Sin consultas este mes.</p>}
        </div>
      </div>
      <div className="tarjeta">
        <span className="etiqueta">Consultas pagadas por día (últimos 60 días)</span>
        {c.porDia.length ? (
          <>
            <div className="barras" role="img" aria-label="Consultas por día">
              {c.porDia.map((d) => <div key={d.dia} style={{ height: `${Math.max(2, (d.pagadas / maximo) * 100)}%` }} title={`${d.dia}: ${d.pagadas} pagadas, ${d.reutilizadas} reutilizadas`} />)}
            </div>
            <div className="fila fila--entre tenue" style={{ fontSize: 12 }}><span>{c.porDia[0].dia}</span><span>{c.porDia[c.porDia.length - 1].dia}</span></div>
          </>
        ) : <p className="tenue">Todavía no hay consultas.</p>}
      </div>
      <div className="tarjeta">
        <div className="fila fila--entre">
          <div>
            <span className="etiqueta">Padrón de SUNAT (para buscar RUC, gratis)</span>
            <p className="suave" style={{ fontSize: 14 }}>
              {c.padron.descargado ? `Descargado el ${fecha(c.padron.descargado)}. Se actualiza solo cada 7 días.` : 'Se descarga solo la primera vez que se busca un RUC.'}
            </p>
          </div>
          {usuario.rol === 'ADMIN' && <button type="button" className="boton-2" onClick={actualizarPadron}>Actualizar ahora</button>}
        </div>
        {aviso && <div className="aviso" role="status">{aviso}</div>}
      </div>
    </>
  );
}
