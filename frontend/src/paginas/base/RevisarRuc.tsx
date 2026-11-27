import { useState } from 'react';
import { api, textoError, type Fila, type Trabajo } from '../../api';
import { ChipRuc } from '../comunes';

const DUDOSOS = ['PROBABLE', 'VARIOS', 'NO_ENCONTRADO', 'INVALIDO'];

const EXPLICA: Record<string, string> = {
  PROBABLE: 'Se encontró un nombre parecido. Confirma que sea la misma empresa.',
  VARIOS: 'Hay varias empresas con ese nombre. Elige la correcta.',
  NO_ENCONTRADO: 'No está en el padrón con ese nombre. Búscala en SUNAT y escribe su RUC, o descártala.',
  INVALIDO: 'El RUC del archivo no es válido (dígito verificador). Corrígelo o descártala.',
};

export function RevisarRuc({ trabajo, onCambio, onListo, onRecargar }: { trabajo: Trabajo; onCambio: (f: Fila) => void; onListo: () => void; onRecargar: () => void }) {
  const dudosas = trabajo.filas.filter((f) => DUDOSOS.includes(f.rucEstado));
  const resueltas = trabajo.filas.filter((f) => ['ELEGIDO', 'DESCARTADA', 'COINCIDENCIA'].includes(f.rucEstado)).length;
  const conOpciones = dudosas.filter((f) => (f.rucEstado === 'PROBABLE' || f.rucEstado === 'VARIOS') && f.opciones.length);
  const totalOpciones = conOpciones.reduce((s, f) => s + f.opciones.length, 0);
  const [aviso, setAviso] = useState('');
  const [ocupado, setOcupado] = useState(false);

  async function agregarTodas(ids?: number[]) {
    const n = ids ? trabajo.filas.find((f) => f.id === ids[0])?.opciones.length ?? 0 : totalOpciones;
    if (!confirm(`Se agregarán hasta ${n} empresas (cada coincidencia como empresa aparte). Consultar cada una en SUNAT gasta 3 consultas. ¿Continuar?`)) return;
    setOcupado(true); setAviso('');
    try {
      const r = await api<{ empresas: number; yaEstaban: number }>(`/trabajos/${trabajo.id}/coincidencias`, { cuerpo: { ids: ids ?? null } });
      setAviso(`Se agregaron ${r.empresas} empresas.${r.yaEstaban ? ` ${r.yaEstaban} ya estaban en la base y se descartaron para no duplicar.` : ''}`);
      onRecargar();
    } catch (e) { setAviso(textoError(e)); }
    finally { setOcupado(false); }
  }

  if (!dudosas.length) {
    return (
      <div className="fila fila--entre" style={{ padding: '8px 0' }}>
        <p>✓ No queda ningún RUC por revisar{resueltas ? ` (${resueltas} revisados a mano)` : ''}.</p>
        <button type="button" className="boton" onClick={onListo}>Siguiente: consultar SUNAT</button>
      </div>
    );
  }
  return (
    <>
      <p className="suave">
        Estas empresas no se pudieron identificar con seguridad. Elige el RUC correcto, escríbelo, o descártala.
        Las que no revises no se consultan ni se descargan (salvo que elijas incluir las probables).
      </p>
      {conOpciones.length > 0 && (
        <div className="nota fila fila--entre">
          <span><b>¿No quieres revisar una por una?</b> Agrega todas las coincidencias como empresas aparte: {conOpciones.length} nombres con {totalOpciones} coincidencias en SUNAT. Las que ya estén en la base no se duplican.</span>
          <button type="button" className="boton boton--chico" disabled={ocupado} onClick={() => agregarTodas()}>Agregar todas las coincidencias</button>
        </div>
      )}
      {aviso && <div className="aviso" role="status">{aviso}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {dudosas.map((f) => <Dudosa key={f.id} trabajoId={trabajo.id} fila={f} onCambio={onCambio} onTodas={() => agregarTodas([f.id])} />)}
      </div>
    </>
  );
}

function Dudosa({ trabajoId, fila, onCambio, onTodas }: { trabajoId: string; fila: Fila; onCambio: (f: Fila) => void; onTodas: () => void }) {
  const [elegido, setElegido] = useState(fila.rucEstado === 'PROBABLE' ? fila.final.ruc : '');
  const [escrito, setEscrito] = useState('');
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const nombre = fila.original.razon || fila.original.ruc || `Fila ${fila.n}`;

  async function enviar(cuerpo: { ruc?: string; descartar?: boolean }) {
    setError(''); setOcupado(true);
    try {
      await api(`/trabajos/${trabajoId}/filas/${fila.id}/ruc`, { cuerpo });
      const op = fila.opciones.find((o) => o.ruc === cuerpo.ruc);
      onCambio({
        ...fila, rucEstado: cuerpo.descartar ? 'DESCARTADA' : 'ELEGIDO',
        final: { ...fila.final, ruc: cuerpo.ruc ?? fila.final.ruc, razon: op?.razon ?? fila.final.razon },
      });
    } catch (e) { setError(textoError(e)); }
    finally { setOcupado(false); }
  }

  const ruc = escrito || elegido;
  return (
    <div className="tarjeta tarjeta--plana" style={{ padding: 16, gap: 10 }}>
      <div className="fila fila--entre">
        <div>
          <span className="tenue numeros" style={{ fontSize: 12 }}>Fila {fila.n} del archivo</span>
          <h3>{nombre}</h3>
        </div>
        <ChipRuc estado={fila.rucEstado} />
      </div>
      <p className="suave" style={{ fontSize: 13 }}>{EXPLICA[fila.rucEstado]}</p>
      {fila.opciones.length > 0 && (
        <fieldset style={{ border: 0, padding: 0, margin: 0, display: 'grid', gap: 6 }}>
          <legend className="oculto-visual">Opciones en SUNAT para {nombre}</legend>
          {fila.opciones.map((o) => (
            <label key={o.ruc} className="opcion-ruc">
              <input type="radio" name={`ruc-${fila.id}`} checked={elegido === o.ruc && !escrito} onChange={() => { setElegido(o.ruc); setEscrito(''); }} />
              <span>
                <b className="numeros">{o.ruc}</b> · {o.razon}
                <span className="tenue"> · {o.estado}{o.condicion ? ` · ${o.condicion}` : ''}{o.direccion ? ` · ${o.direccion}` : ''}</span>
              </span>
            </label>
          ))}
        </fieldset>
      )}
      <div className="fila">
        <label className="oculto-visual" htmlFor={`escrito-${fila.id}`}>Escribir RUC</label>
        <input id={`escrito-${fila.id}`} className="entrada numeros" style={{ maxWidth: 200 }} inputMode="numeric" maxLength={11}
          placeholder={fila.opciones.length ? 'U otro RUC…' : 'RUC de 11 dígitos'} value={escrito}
          onChange={(e) => setEscrito(e.target.value.replace(/\D/g, '').slice(0, 11))} />
        <button type="button" className="boton" disabled={ocupado || ruc.length !== 11} onClick={() => enviar({ ruc })}>Usar este RUC</button>
        {fila.opciones.length > 1 && <button type="button" className="boton-2" disabled={ocupado} onClick={onTodas}>Agregar las {fila.opciones.length}</button>}
        <button type="button" className="boton-2" disabled={ocupado} onClick={() => enviar({ descartar: true })}>Descartar</button>
        <a href="https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp" target="_blank" rel="noopener noreferrer" style={{ fontSize: 13 }}>
          Buscar en SUNAT ↗
        </a>
      </div>
      {error && <div className="alerta" role="alert">{error}</div>}
    </div>
  );
}
