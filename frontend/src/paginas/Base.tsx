import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, fecha, textoError, type Fila, type Trabajo } from '../api';
import { useSesion } from '../sesion';
import { ChipEstado } from './comunes';
import { RevisarRuc } from './base/RevisarRuc';
import { ConsultarSunat } from './base/ConsultarSunat';
import { Empresas } from './base/Empresas';
import { Descargar } from './base/Descargar';

const DUDOSOS = ['PROBABLE', 'VARIOS', 'NO_ENCONTRADO', 'INVALIDO'];
const CONFIABLES = ['DEL_ARCHIVO', 'EXACTO', 'ELEGIDO', 'COINCIDENCIA'];
type Pestana = 'ruc' | 'sunat' | 'empresas' | 'descargar';

export function Base() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { usuario } = useSesion();
  const [t, setT] = useState<Trabajo | null>(null);
  const [error, setError] = useState('');
  const [pestana, setPestana] = useState<Pestana | null>(null);

  const cargar = useCallback(() => api<Trabajo>(`/trabajos/${id}`).then(setT).catch((e) => setError(textoError(e))), [id]);
  useEffect(() => { cargar(); }, [cargar]);

  const enProceso = t?.estado === 'BUSCANDO_RUC' || t?.estado === 'CARGADO' || t?.estado === 'CONSULTANDO';
  useEffect(() => {
    if (!enProceso) return;
    const i = setInterval(cargar, 2000);
    return () => clearInterval(i);
  }, [enProceso, cargar]);

  const cuentas = useMemo(() => {
    const f = t?.filas ?? [];
    return {
      total: f.length,
      dudosos: f.filter((x) => DUDOSOS.includes(x.rucEstado)).length,
      confiables: f.filter((x) => CONFIABLES.includes(x.rucEstado)).length,
      descartadas: f.filter((x) => x.rucEstado === 'DESCARTADA').length,
      consultadas: f.filter((x) => x.consultada).length,
      completas: f.filter((x) => CONFIABLES.includes(x.rucEstado) && x.faltan.length === 0).length,
    };
  }, [t]);

  // Pestaña por defecto según en qué va la base
  const activa: Pestana = pestana ?? (cuentas.dudosos > 0 && t?.estado === 'REVISAR_RUC' ? 'ruc' : cuentas.consultadas === 0 && t?.estado === 'REVISAR_RUC' ? 'sunat' : 'empresas');

  function actualizarFila(fila: Fila) {
    setT((x) => (x ? { ...x, filas: x.filas.map((f) => (f.id === fila.id ? fila : f)) } : x));
  }

  async function borrar() {
    if (!t || !confirm(`¿Borrar la base "${t.nombre}"? Se pierde lo revisado (las consultas ya pagadas quedan guardadas).`)) return;
    try { await api(`/trabajos/${t.id}`, { metodo: 'DELETE' }); navegar('/'); }
    catch (e) { setError(textoError(e)); }
  }

  async function reintentar() {
    try { await api(`/trabajos/${id}/reintentar`, { metodo: 'POST' }); cargar(); }
    catch (e) { setError(textoError(e)); }
  }

  if (!t) return error ? <div className="alerta" role="alert">{error}</div> : <p className="tenue">Cargando…</p>;

  const pasos = [
    { titulo: 'Buscar RUC', texto: 'Padrón de SUNAT, gratis', hecho: !['CARGADO', 'BUSCANDO_RUC', 'ERROR'].includes(t.estado), actual: t.estado === 'BUSCANDO_RUC' },
    { titulo: 'Revisar RUC', texto: cuentas.dudosos ? `${cuentas.dudosos} por revisar` : 'Sin dudas', hecho: t.estado !== 'BUSCANDO_RUC' && cuentas.dudosos === 0, actual: activa === 'ruc' },
    { titulo: 'Consultar SUNAT', texto: `${cuentas.consultadas} de ${cuentas.confiables} consultadas`, hecho: cuentas.consultadas > 0, actual: activa === 'sunat' || t.estado === 'CONSULTANDO' },
    { titulo: 'Revisar y completar', texto: `${cuentas.completas} completas`, hecho: cuentas.completas > 0 && cuentas.completas === cuentas.confiables, actual: activa === 'empresas' },
    { titulo: 'Descargar', texto: t.descargas ? `${t.descargas} descarga${t.descargas > 1 ? 's' : ''}` : 'Plantilla del CRM', hecho: t.descargas > 0, actual: activa === 'descargar' },
  ];

  return (
    <>
      <div className="encabezado">
        <div>
          <p style={{ marginTop: 0 }}><Link to="/">← Bases</Link></p>
          <h1>{t.nombre}</h1>
          <p className="fila" style={{ gap: 8 }}>
            <ChipEstado estado={t.estado} />
            <span>{cuentas.total} empresas · subida por {t.creadoPor} el {fecha(t.creadoAt)}</span>
          </p>
        </div>
        {(t.creadoPorId === usuario.id || usuario.rol === 'ADMIN') && !enProceso && (
          <button type="button" className="boton-texto boton-texto--peligro" onClick={borrar}>Borrar base</button>
        )}
      </div>

      <ol className="pasos" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {pasos.map((p) => (
          <li key={p.titulo} className={`paso${p.hecho ? ' paso--hecho' : ''}${p.actual ? ' paso--actual' : ''}`}><b>{p.titulo}</b>{p.texto}</li>
        ))}
      </ol>

      {enProceso && (
        <div className="tarjeta" aria-live="polite">
          <div className="fila fila--entre">
            <b>{t.mensaje || (t.estado === 'CONSULTANDO' ? 'Consultando SUNAT…' : 'Buscando RUC en el padrón de SUNAT…')}</b>
            {t.estado === 'CONSULTANDO' && t.total > 0 && <span className="numeros tenue">{t.progreso} de {t.total}</span>}
          </div>
          <div className={`barra-progreso${t.estado === 'CONSULTANDO' && t.total ? '' : ' barra-progreso--indeterminada'}`}>
            <span style={{ width: `${t.total ? Math.round((t.progreso / t.total) * 100) : 0}%` }} />
          </div>
          <p className="tenue" style={{ fontSize: 13 }}>
            {t.estado === 'CONSULTANDO' ? 'Puedes cerrar esta página: la consulta sigue y se guarda sola.' : 'La primera búsqueda del día puede tardar unos minutos (se descarga el padrón de SUNAT).'}
          </p>
        </div>
      )}
      {t.estado === 'ERROR' && (
        <div className="alerta fila fila--entre" role="alert"><span>{t.mensaje}</span><button type="button" className="boton boton--chico" onClick={reintentar}>Reintentar</button></div>
      )}
      {t.mensaje && t.estado === 'REVISION' && <div className="nota nota--ambar">{t.mensaje}</div>}
      {error && <div className="alerta" role="alert">{error}</div>}

      {!['CARGADO', 'BUSCANDO_RUC', 'ERROR'].includes(t.estado) && (
        <div className="tarjeta">
          <div className="pestanas" role="tablist">
            <button role="tab" aria-selected={activa === 'ruc'} onClick={() => setPestana('ruc')}>
              RUC por revisar {cuentas.dudosos > 0 && <span className="chip chip--ambar">{cuentas.dudosos}</span>}
            </button>
            <button role="tab" aria-selected={activa === 'sunat'} onClick={() => setPestana('sunat')}>Consultar SUNAT</button>
            <button role="tab" aria-selected={activa === 'empresas'} onClick={() => setPestana('empresas')}>
              Empresas <span className="chip chip--gris">{cuentas.total - cuentas.descartadas}</span>
            </button>
            <button role="tab" aria-selected={activa === 'descargar'} onClick={() => setPestana('descargar')}>Descargar</button>
          </div>
          {activa === 'ruc' && <RevisarRuc trabajo={t} onCambio={actualizarFila} onListo={() => setPestana('sunat')} onRecargar={cargar} />}
          {activa === 'sunat' && <ConsultarSunat trabajo={t} onIniciada={() => { cargar(); setPestana('empresas'); }} />}
          {activa === 'empresas' && <Empresas trabajo={t} onCambio={actualizarFila} onRecargar={cargar} />}
          {activa === 'descargar' && <Descargar trabajo={t} onDescargado={() => setTimeout(cargar, 1500)} />}
        </div>
      )}
    </>
  );
}
