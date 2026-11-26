import { Fragment, useMemo, useState } from 'react';
import { api, textoError, type Fila, type Trabajo } from '../../api';
import { ChipRuc } from '../comunes';

const OPERADORES = ['movistar', 'claro', 'entel', 'bitel'];
const SEGMENTOS = ['Micro', 'Pequeña', 'Mediana', 'Grande'];
const POR_PAGINA = 50;
const sinTildes = (t: string) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

export function Empresas({ trabajo, onCambio, onRecargar }: { trabajo: Trabajo; onCambio: (f: Fila) => void; onRecargar: () => void }) {
  const [busca, setBusca] = useState('');
  const [segmento, setSegmento] = useState('todos');
  const [filtro, setFiltro] = useState('todas');
  const [pagina, setPagina] = useState(0);
  const [abierta, setAbierta] = useState<number | null>(null);

  const filas = useMemo(() => {
    const q = sinTildes(busca.trim());
    return trabajo.filas.filter((f) => {
      if (f.rucEstado === 'DESCARTADA' && filtro !== 'descartadas') return false;
      if (filtro === 'descartadas' && f.rucEstado !== 'DESCARTADA') return false;
      if (filtro === 'faltan' && !f.faltan.length) return false;
      if (filtro === 'sin-lineas' && f.final.lineas !== null) return false;
      if (filtro === 'sin-consultar' && f.consultada) return false;
      const s = f.final.segmento;
      if (segmento === 'micro' && s !== 'Micro') return false;
      if (segmento === 'pyme' && s !== 'Pequeña' && s !== 'Mediana') return false;
      if (segmento === 'grande' && s !== 'Grande') return false;
      if (segmento === 'sin' && s) return false;
      return !q || sinTildes(`${f.final.ruc} ${f.final.razon} ${f.final.nombre_archivo} ${f.final.representante}`).includes(q);
    });
  }, [trabajo.filas, busca, segmento, filtro]);

  const paginas = Math.max(1, Math.ceil(filas.length / POR_PAGINA));
  const visibles = filas.slice(pagina * POR_PAGINA, (pagina + 1) * POR_PAGINA);
  const cambiaFiltro = <T,>(f: (v: T) => void) => (v: T) => { f(v); setPagina(0); setAbierta(null); };

  return (
    <>
      <div className="fila">
        <input className="entrada" style={{ maxWidth: 300 }} placeholder="Buscar RUC, empresa o representante" aria-label="Buscar" value={busca} onChange={(e) => cambiaFiltro(setBusca)(e.target.value)} />
        <select className="selector" style={{ maxWidth: 210 }} aria-label="Segmento" value={segmento} onChange={(e) => cambiaFiltro(setSegmento)(e.target.value)}>
          <option value="todos">Todos los segmentos</option>
          <option value="micro">Solo micro</option>
          <option value="pyme">Solo pymes (pequeña y mediana)</option>
          <option value="grande">Solo grandes</option>
          <option value="sin">Sin segmento</option>
        </select>
        <select className="selector" style={{ maxWidth: 230 }} aria-label="Mostrar" value={filtro} onChange={(e) => cambiaFiltro(setFiltro)(e.target.value)}>
          <option value="todas">Todas</option>
          <option value="faltan">Les falta algún dato</option>
          <option value="sin-lineas">Sin líneas registradas</option>
          <option value="sin-consultar">Sin consultar en SUNAT</option>
          <option value="descartadas">Descartadas</option>
        </select>
        <span className="tenue numeros" style={{ marginLeft: 'auto', fontSize: 13 }}>{filas.length} empresas</span>
      </div>
      <p className="tenue" style={{ fontSize: 13 }}>Haz clic en una empresa para elegir el representante, corregir datos, marcar el segmento y anotar sus líneas por operador.</p>

      <div className="tabla-caja">
        <table className="tabla">
          <thead>
            <tr>
              <th>Fila</th><th>RUC</th><th>Razón social</th><th>Representante</th><th>DNI</th><th>Teléfono</th>
              <th>Distrito</th><th>Segmento</th><th className="celda-num">Líneas</th><th>Operador</th><th>Falta</th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((f) => (
              <Fragment key={f.id}>
                <tr className={`fila--clic${abierta === f.id ? ' fila--abierta' : ''}`} onClick={() => setAbierta(abierta === f.id ? null : f.id)}
                  tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setAbierta(abierta === f.id ? null : f.id); } }}
                  aria-expanded={abierta === f.id}>
                  <td className="numeros tenue">{f.n}</td>
                  <td className="numeros">{f.final.ruc || <ChipRuc estado={f.rucEstado} />}</td>
                  <td><div className="ellipsis" title={f.final.razon}>{f.final.razon || f.final.nombre_archivo}</div>
                    {!f.final.activo && <span className="chip chip--alerta">{f.final.estado_sunat}</span>}</td>
                  <td><div className="ellipsis" style={{ maxWidth: 200 }}>{f.final.representante || <span className="tenue">—</span>}</div></td>
                  <td className="numeros">{f.final.dni || <span className="tenue">—</span>}</td>
                  <td className="numeros">{f.final.telefono || <span className="tenue">—</span>}</td>
                  <td>{f.final.distrito || <span className="tenue">—</span>}</td>
                  <td>{f.final.segmento || <span className="tenue">—</span>}</td>
                  <td className="celda-num numeros">{f.final.lineas ?? <span className="tenue">—</span>}</td>
                  <td>{f.final.operador || <span className="tenue">—</span>}</td>
                  <td>{f.faltan.length ? <span className="chip chip--ambar" title={f.faltan.join(', ')}>{f.faltan.length}</span> : <span className="chip chip--ok">✓</span>}</td>
                </tr>
                {abierta === f.id && (
                  <tr><td colSpan={11} style={{ background: '#fbfdf8' }}><Editor trabajoId={trabajo.id} fila={f} onCambio={onCambio} onCerrar={() => setAbierta(null)} onRecargar={onRecargar} /></td></tr>
                )}
              </Fragment>
            ))}
            {!visibles.length && <tr><td colSpan={11} className="tenue" style={{ padding: 20, textAlign: 'center' }}>No hay empresas con estos filtros.</td></tr>}
          </tbody>
        </table>
      </div>
      {paginas > 1 && (
        <div className="fila" style={{ justifyContent: 'center' }}>
          <button type="button" className="boton-2 boton--chico" disabled={pagina === 0} onClick={() => { setPagina(pagina - 1); setAbierta(null); }}>← Anterior</button>
          <span className="numeros suave" style={{ fontSize: 13 }}>Página {pagina + 1} de {paginas}</span>
          <button type="button" className="boton-2 boton--chico" disabled={pagina >= paginas - 1} onClick={() => { setPagina(pagina + 1); setAbierta(null); }}>Siguiente →</button>
        </div>
      )}
    </>
  );
}

function Editor({ trabajoId, fila, onCambio, onCerrar, onRecargar }: { trabajoId: string; fila: Fila; onCambio: (f: Fila) => void; onCerrar: () => void; onRecargar: () => void }) {
  const f = fila.final;
  const d = fila.datos;
  const reps = fila.representantes;
  const repElegido = typeof d.rep === 'number' ? d.rep : 0;
  const [modoRep, setModoRep] = useState<number | 'manual'>('representante' in d || !reps.length ? 'manual' : repElegido);
  const [rep, setRep] = useState({ nombre: f.representante, dni: f.dni, cargo: f.cargo });
  const [telefono, setTelefono] = useState(f.telefono);
  const [correo, setCorreo] = useState(f.correo);
  const [segmento, setSegmento] = useState(f.segmento);
  const [lineas, setLineas] = useState<Record<string, string>>(() =>
    Object.fromEntries(OPERADORES.map((o) => [o, f.lineas_por[o] !== undefined ? String(f.lineas_por[o]) : ''])));
  const [observacion, setObservacion] = useState(f.observacion);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const telefonos = [...new Set([f.telefono, ...f.otros_telefonos].filter(Boolean))];
  const correos = [...new Set([f.correo, ...f.otros_correos].filter(Boolean))];
  const totalLineas = OPERADORES.reduce((s, o) => s + (Number(lineas[o]) || 0), 0);
  const hayLineas = OPERADORES.some((o) => lineas[o] !== '');

  async function guardar() {
    setError(''); setOcupado(true);
    // Solo se envía lo que cambió: lo demás sigue tomando el dato de SUNAT o del archivo
    const cuerpo: Record<string, unknown> = {};
    if (telefono !== f.telefono) cuerpo.telefono = telefono;
    if (correo !== f.correo) cuerpo.correo = correo;
    if (segmento !== f.segmento) cuerpo.segmento = segmento || null;
    if (observacion !== f.observacion) cuerpo.observacion = observacion;
    if (modoRep === 'manual') {
      if (rep.nombre !== f.representante || rep.dni !== f.dni || rep.cargo !== f.cargo) Object.assign(cuerpo, { representante: rep.nombre, dni: rep.dni, cargo: rep.cargo });
    } else if (modoRep !== repElegido || 'representante' in d) cuerpo.rep = modoRep;
    const original = Object.fromEntries(OPERADORES.map((o) => [o, f.lineas_por[o] !== undefined ? String(f.lineas_por[o]) : '']));
    if (JSON.stringify(original) !== JSON.stringify(lineas)) {
      if (hayLineas) cuerpo.lineas_por = Object.fromEntries(OPERADORES.map((o) => [o, lineas[o] === '' ? null : Number(lineas[o])]));
      else cuerpo.quitar = ['lineas_por'];
    }
    if (!Object.keys(cuerpo).length) { setOcupado(false); onCerrar(); return; }
    try {
      const r = await api<Fila>(`/trabajos/${trabajoId}/filas/${fila.id}`, { metodo: 'PATCH', cuerpo });
      onCambio({ ...r, opciones: fila.opciones });
      onCerrar();
    } catch (e) { setError(textoError(e)); }
    finally { setOcupado(false); }
  }

  return (
    <div className="detalle">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <h3>{f.razon || f.nombre_archivo}</h3>
          <p className="tenue" style={{ fontSize: 13 }}>
            RUC {f.ruc || '—'} · {f.estado_sunat || 'sin datos del padrón'} · {f.como_ruc}
            {f.direccion && <><br />{f.direccion} · {[f.distrito, f.provincia, f.departamento].filter(Boolean).join(', ')}</>}
            {f.nombre_archivo && f.nombre_archivo !== f.razon && <><br />En el archivo: {f.nombre_archivo}</>}
          </p>
          <CambiarRuc trabajoId={trabajoId} fila={fila} onListo={() => { onCerrar(); onRecargar(); }} />
        </div>

        <fieldset style={{ border: 0, padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <legend className="etiqueta" style={{ marginBottom: 6 }}>Representante legal</legend>
          {reps.map((r, i) => (
            <label key={i} className="opcion-ruc">
              <input type="radio" name={`rep-${fila.id}`} checked={modoRep === i} onChange={() => setModoRep(i)} />
              <span><b>{r.nombre}</b> <span className="tenue">· {r.cargo || 'sin cargo'}{r.dni ? ` · DNI ${r.dni}` : r.documento ? ` · ${r.tipo} ${r.documento}` : ''}{r.desde ? ` · desde ${r.desde.slice(0, 4)}` : ''}</span></span>
            </label>
          ))}
          <label className="opcion-ruc">
            <input type="radio" name={`rep-${fila.id}`} checked={modoRep === 'manual'} onChange={() => setModoRep('manual')} />
            <span>{reps.length ? 'Escribir otro' : fila.consultada ? 'SUNAT no tiene representantes: escríbelo' : 'Aún sin consultar en SUNAT: escríbelo si lo sabes'}</span>
          </label>
          {modoRep === 'manual' && (
            <div className="rejilla" style={{ gridTemplateColumns: '2fr 1fr 1.3fr' }}>
              <input className="entrada entrada--chica" aria-label="Nombre del representante" placeholder="Nombre completo" value={rep.nombre} onChange={(e) => setRep({ ...rep, nombre: e.target.value })} />
              <input className="entrada entrada--chica numeros" aria-label="DNI" placeholder="DNI" inputMode="numeric" maxLength={8} value={rep.dni} onChange={(e) => setRep({ ...rep, dni: e.target.value.replace(/\D/g, '') })} />
              <input className="entrada entrada--chica" aria-label="Cargo" placeholder="Cargo" value={rep.cargo} onChange={(e) => setRep({ ...rep, cargo: e.target.value })} />
            </div>
          )}
        </fieldset>

        <div className="rejilla" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <div className="campo">
            <label className="etiqueta" htmlFor={`tel-${fila.id}`}>Teléfono</label>
            <input id={`tel-${fila.id}`} className="entrada entrada--chica numeros" list={`tels-${fila.id}`} value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="9XXXXXXXX" />
            <datalist id={`tels-${fila.id}`}>{telefonos.map((t) => <option key={t} value={t} />)}</datalist>
            {telefonos.length > 1 && <span className="tenue" style={{ fontSize: 12 }}>De SUNAT: {telefonos.join(', ')}</span>}
          </div>
          <div className="campo">
            <label className="etiqueta" htmlFor={`correo-${fila.id}`}>Correo</label>
            <input id={`correo-${fila.id}`} className="entrada entrada--chica" list={`correos-${fila.id}`} value={correo} onChange={(e) => setCorreo(e.target.value)} />
            <datalist id={`correos-${fila.id}`}>{correos.map((t) => <option key={t} value={t} />)}</datalist>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="campo">
          <label className="etiqueta" htmlFor={`seg-${fila.id}`}>Segmento</label>
          <select id={`seg-${fila.id}`} className="selector" value={segmento} onChange={(e) => setSegmento(e.target.value)}>
            <option value="">Sin definir</option>
            {SEGMENTOS.map((s) => <option key={s}>{s}</option>)}
          </select>
          <span className="tenue" style={{ fontSize: 12 }}>
            {f.trabajadores !== null ? `${f.trabajadores} trabajadores en planilla (${f.periodo}) → estimado: ${f.segmento_estimado}. Micro hasta 10, pequeña hasta 100, mediana hasta 250.` : 'Sin dato de trabajadores: decide por lo que sepas de la empresa.'}
          </span>
        </div>
        <div className="campo">
          <span className="etiqueta">Líneas por operador</span>
          <div className="lineas">
            {OPERADORES.map((o) => (
              <label key={o}>{o[0].toUpperCase() + o.slice(1)}
                <input className="entrada entrada--chica entrada--num numeros" inputMode="numeric" value={lineas[o]} maxLength={6}
                  onChange={(e) => setLineas({ ...lineas, [o]: e.target.value.replace(/\D/g, '') })} />
              </label>
            ))}
          </div>
          <span className="tenue" style={{ fontSize: 12 }}>
            {hayLineas ? `Total ${totalLineas}; el operador será el que tenga más líneas.` : f.lineas !== null ? `Del archivo: ${f.lineas} líneas${f.operador ? ` con ${f.operador}` : ''}.` : 'Déjalo vacío si no lo sabes.'}
          </span>
        </div>
        <div className="campo">
          <label className="etiqueta" htmlFor={`obs-${fila.id}`}>Observación</label>
          <input id={`obs-${fila.id}`} className="entrada entrada--chica" maxLength={200} value={observacion} onChange={(e) => setObservacion(e.target.value)} />
        </div>
        {error && <div className="alerta" role="alert">{error}</div>}
        <div className="fila" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="boton-2 boton--chico" onClick={onCerrar}>Cancelar</button>
          <button type="button" className="boton boton--chico" disabled={ocupado} onClick={guardar}>{ocupado ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </div>
    </div>
  );
}

/** Corregir un RUC mal elegido (o recuperar una empresa descartada) */
function CambiarRuc({ trabajoId, fila, onListo }: { trabajoId: string; fila: Fila; onListo: () => void }) {
  const [abierto, setAbierto] = useState(fila.rucEstado === 'DESCARTADA');
  const [ruc, setRuc] = useState('');
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const descartada = fila.rucEstado === 'DESCARTADA';

  async function enviar(cuerpo: { ruc?: string; descartar?: boolean }) {
    if (cuerpo.descartar && !confirm('¿Descartar esta empresa? No se consultará ni saldrá en el Excel.')) return;
    setError(''); setOcupado(true);
    try { await api(`/trabajos/${trabajoId}/filas/${fila.id}/ruc`, { cuerpo }); onListo(); }
    catch (e) { setError(textoError(e)); setOcupado(false); }
  }

  if (!abierto) {
    return (
      <div className="fila" style={{ marginTop: 6 }}>
        <button type="button" className="boton-texto" onClick={() => setAbierto(true)}>¿RUC equivocado? Cambiar RUC</button>
      </div>
    );
  }
  return (
    <div className="nota" style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span>{descartada ? 'Esta empresa está descartada. Para recuperarla, escribe su RUC.' : 'Escribe el RUC correcto. Se borran los datos de SUNAT del RUC anterior y la empresa vuelve a quedar por consultar.'}</span>
      <div className="fila">
        <label className="oculto-visual" htmlFor={`nuevo-ruc-${fila.id}`}>RUC correcto</label>
        <input id={`nuevo-ruc-${fila.id}`} className="entrada entrada--chica numeros" style={{ maxWidth: 170 }} inputMode="numeric" maxLength={11}
          placeholder="RUC de 11 dígitos" value={ruc} onChange={(e) => setRuc(e.target.value.replace(/\D/g, '').slice(0, 11))} />
        <button type="button" className="boton boton--chico" disabled={ocupado || ruc.length !== 11} onClick={() => enviar({ ruc })}>Usar este RUC</button>
        {!descartada && <button type="button" className="boton-2 boton--chico" disabled={ocupado} onClick={() => enviar({ descartar: true })}>Descartar empresa</button>}
        <a href="https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp" target="_blank" rel="noopener noreferrer" style={{ fontSize: 13 }}>Buscar en SUNAT ↗</a>
        {!descartada && <button type="button" className="boton-texto" onClick={() => setAbierto(false)}>Cancelar</button>}
      </div>
      {error && <div className="alerta" role="alert">{error}</div>}
    </div>
  );
}
