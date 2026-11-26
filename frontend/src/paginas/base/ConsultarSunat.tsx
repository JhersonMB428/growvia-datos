import { useEffect, useState } from 'react';
import { api, textoError, type Estimado, type Trabajo } from '../../api';

const DATOS = [
  { clave: 'representantes', titulo: 'Representante legal y DNI', texto: 'Nombre, cargo y DNI de los representantes registrados en SUNAT.' },
  { clave: 'contacto', titulo: 'Teléfonos y correos', texto: 'Los que la empresa declaró a SUNAT (no siempre los tiene).' },
  { clave: 'trabajadores', titulo: 'Trabajadores en planilla', texto: 'Para separar micro, pequeñas, medianas y grandes.' },
];

export function ConsultarSunat({ trabajo, onIniciada }: { trabajo: Trabajo; onIniciada: () => void }) {
  const [endpoints, setEndpoints] = useState<string[]>(['representantes', 'contacto', 'trabajadores']);
  const [incluirProbables, setIncluirProbables] = useState(false);
  const [excluirInactivas, setExcluirInactivas] = useState(true);
  const [limite, setLimite] = useState('');
  const [estimado, setEstimado] = useState<Estimado | null>(null);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const enCurso = trabajo.estado === 'CONSULTANDO';

  const cuerpo = { endpoints, incluirProbables, excluirInactivas, limite: limite ? Number(limite) : null };
  const clave = JSON.stringify(cuerpo);

  useEffect(() => {
    if (!endpoints.length) return;
    let vigente = true;
    const t = setTimeout(() => {
      api<Estimado>(`/trabajos/${trabajo.id}/consultar`, { cuerpo: JSON.parse(clave) })
        .then((e) => { if (vigente) { setEstimado(e); setError(''); } })
        .catch((e) => { if (vigente) setError(textoError(e)); });
    }, 250);
    return () => { vigente = false; clearTimeout(t); };
  }, [clave, trabajo.id, endpoints.length, trabajo.filas]);

  async function consultar() {
    if (!estimado) return;
    if (!confirm(`Se consultarán ${estimado.empresas} empresas y se gastarán ${estimado.consultas} consultas del plan. ¿Continuar?`)) return;
    setOcupado(true); setError('');
    try {
      await api(`/trabajos/${trabajo.id}/consultar`, { cuerpo: { ...cuerpo, confirmar: true } });
      onIniciada();
    } catch (e) { setError(textoError(e)); }
    finally { setOcupado(false); }
  }

  const alterna = (c: string) => setEndpoints((x) => (x.includes(c) ? x.filter((y) => y !== c) : [...x, c]));
  const usoTras = estimado ? estimado.usadasMes + estimado.consultas : 0;
  const listo = endpoints.length > 0 && estimado !== null;

  return (
    <div style={{ display: 'grid', gap: 18, gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <p className="suave">Se consultan solo las empresas con RUC confirmado que aún no se consultaron. Lo ya consultado en los últimos 60 días se reutiliza sin gastar.</p>
        <fieldset style={{ border: 0, margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <legend className="etiqueta" style={{ marginBottom: 8 }}>¿Qué datos traer? (cada uno es 1 consulta por empresa)</legend>
          {DATOS.map((d) => (
            <label key={d.clave} className="casilla" style={{ alignItems: 'flex-start' }}>
              <input type="checkbox" checked={endpoints.includes(d.clave)} onChange={() => alterna(d.clave)} style={{ marginTop: 2 }} />
              <span><b>{d.titulo}</b><br /><span className="tenue" style={{ fontSize: 13 }}>{d.texto}</span></span>
            </label>
          ))}
        </fieldset>
        <div className="etiqueta">Opciones</div>
        <label className="casilla"><input type="checkbox" checked={excluirInactivas} onChange={(e) => setExcluirInactivas(e.target.checked)} />No consultar empresas de baja o suspendidas</label>
        <label className="casilla"><input type="checkbox" checked={incluirProbables} onChange={(e) => setIncluirProbables(e.target.checked)} />Incluir las de RUC "probable" sin revisar</label>
        <div className="campo" style={{ maxWidth: 260 }}>
          <label className="etiqueta" htmlFor="limite">Consultar solo las primeras… (opcional)</label>
          <input id="limite" className="entrada numeros" inputMode="numeric" placeholder="Todas" value={limite} onChange={(e) => setLimite(e.target.value.replace(/\D/g, '').slice(0, 5))} />
        </div>
      </div>

      <div className="tarjeta tarjeta--plana" style={{ background: '#fbfcfa' }}>
        <h3>Resumen antes de consultar</h3>
        {!endpoints.length ? <p className="tenue">Elige al menos un dato.</p> : !estimado ? <p className="tenue">Calculando…</p> : (
          <>
            <div className="rejilla" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <div><div className="cifra numeros">{estimado.empresas}</div><span className="suave">empresas</span></div>
              <div><div className="cifra numeros">{estimado.consultas}</div><span className="suave">consultas que se gastarán</span></div>
            </div>
            <div>
              <div className="fila fila--entre" style={{ fontSize: 13 }}>
                <span>Plan de este mes</span>
                <span className="numeros">{usoTras.toLocaleString('es-PE')} de {estimado.limiteMes.toLocaleString('es-PE')} después de esta consulta</span>
              </div>
              <div className={`medidor${!estimado.alcanza ? ' medidor--alto' : ''}`} style={{ marginTop: 6 }}>
                <span style={{ width: `${Math.min(100, (usoTras / Math.max(1, estimado.limiteMes)) * 100)}%` }} />
              </div>
            </div>
            {!estimado.tokenActivo && <div className="nota nota--ambar">Falta configurar el token de apiconsulta. Pídeselo al administrador.</div>}
            {!estimado.alcanza && (
              <div className="nota nota--ambar">
                No alcanzan las consultas del mes (quedan {estimado.quedan}). Pon un límite de empresas o pide pasar al plan Plus.
              </div>
            )}
            {error && <div className="alerta" role="alert">{error}</div>}
            <button type="button" className="boton" disabled={!listo || ocupado || enCurso || !estimado.empresas || !estimado.alcanza || !estimado.tokenActivo} onClick={consultar}>
              {enCurso ? 'Consulta en curso…' : ocupado ? 'Iniciando…' : estimado.empresas ? `Consultar ${estimado.empresas} empresas` : 'No hay empresas por consultar'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
