import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, fecha, textoError, type Actividad, type UsuarioAcceso } from '../api';
import { useSesion } from '../sesion';

const ACCIONES: Record<string, string> = {
  INGRESO: 'Entró', INGRESO_SIN_ACCESO: 'Intentó entrar sin acceso', ACCESO_DADO: 'Dio acceso', ACCESO_CAMBIADO: 'Cambió un acceso',
  BASE_SUBIDA: 'Subió una base', BASE_BORRADA: 'Borró una base', CONSULTA_INICIADA: 'Inició una consulta a SUNAT',
  CONSULTA_TERMINADA: 'Terminó una consulta a SUNAT', EXCEL_DESCARGADO: 'Descargó un Excel', PADRON_ACTUALIZADO: 'Actualizó el padrón',
};

function resumen(a: Actividad) {
  const d = a.detalle ?? {};
  const partes = [d.email, d.rol && `rol ${d.rol}`, d.activo === false && 'desactivado', d.activo === true && 'activado', d.archivo, d.filas && `${d.filas} filas`,
    d.empresas && `${d.empresas} empresas`, d.consultas && `${d.consultas} consultas`, d.nombre];
  return partes.filter(Boolean).join(' · ');
}

export function Accesos() {
  const { usuario } = useSesion();
  const [usuarios, setUsuarios] = useState<UsuarioAcceso[]>([]);
  const [actividad, setActividad] = useState<Actividad[]>([]);
  const [email, setEmail] = useState('');
  const [nombre, setNombre] = useState('');
  const [rol, setRol] = useState<'USUARIO' | 'ADMIN'>('USUARIO');
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  const cargar = useCallback(() => {
    api<UsuarioAcceso[]>('/usuarios').then(setUsuarios).catch((e) => setError(textoError(e)));
    api<Actividad[]>('/usuarios/actividad').then(setActividad).catch(() => undefined);
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  async function agregar(e: FormEvent) {
    e.preventDefault();
    setError(''); setAviso('');
    try {
      await api('/usuarios', { cuerpo: { email, nombre, rol } });
      setAviso(`Listo: ${email} ya puede entrar con un código a su correo.`);
      setEmail(''); setNombre(''); setRol('USUARIO');
      cargar();
    } catch (err) { setError(textoError(err)); }
  }

  async function cambiar(u: UsuarioAcceso, cambio: Partial<Pick<UsuarioAcceso, 'rol' | 'activo'>>) {
    setError(''); setAviso('');
    try { await api(`/usuarios/${u.id}`, { metodo: 'PATCH', cuerpo: cambio }); cargar(); }
    catch (err) { setError(textoError(err)); }
  }

  return (
    <>
      <div className="encabezado">
        <div>
          <h1>Accesos</h1>
          <p>Solo los correos de esta lista pueden entrar. Entran con un código que llega a su correo (sin contraseña).</p>
        </div>
      </div>

      <form className="tarjeta" onSubmit={agregar}>
        <h2>Dar acceso a un correo</h2>
        <div className="rejilla" style={{ gridTemplateColumns: '2fr 1.5fr 1fr auto', alignItems: 'end' }}>
          <div className="campo"><label className="etiqueta" htmlFor="nuevo-email">Correo</label>
            <input id="nuevo-email" className="entrada" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nombre@corevia.global" /></div>
          <div className="campo"><label className="etiqueta" htmlFor="nuevo-nombre">Nombre (opcional)</label>
            <input id="nuevo-nombre" className="entrada" value={nombre} onChange={(e) => setNombre(e.target.value)} /></div>
          <div className="campo"><label className="etiqueta" htmlFor="nuevo-rol">Rol</label>
            <select id="nuevo-rol" className="selector" value={rol} onChange={(e) => setRol(e.target.value as 'USUARIO' | 'ADMIN')}>
              <option value="USUARIO">Usuario</option><option value="ADMIN">Administrador</option>
            </select></div>
          <button className="boton" disabled={!email.includes('@')}>Dar acceso</button>
        </div>
        <p className="tenue" style={{ fontSize: 13 }}><b>Usuario</b>: sube bases, consulta SUNAT y descarga. <b>Administrador</b>: además da accesos y ve la actividad.</p>
        {aviso && <div className="aviso" role="status">{aviso}</div>}
        {error && <div className="alerta" role="alert">{error}</div>}
      </form>

      <div className="tarjeta">
        <h2>Correos con acceso</h2>
        <div className="tabla-caja">
          <table className="tabla">
            <thead><tr><th>Correo</th><th>Nombre</th><th>Rol</th><th>Estado</th><th>Último ingreso</th><th>Agregado por</th><th /></tr></thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id} style={u.activo ? undefined : { opacity: 0.55 }}>
                  <td>{u.email}{u.id === usuario.id && <span className="tenue"> (tú)</span>}</td>
                  <td>{u.nombre || '—'}</td>
                  <td>
                    <select className="selector entrada--chica" style={{ width: 150 }} aria-label={`Rol de ${u.email}`} value={u.rol} disabled={u.id === usuario.id}
                      onChange={(e) => cambiar(u, { rol: e.target.value as 'USUARIO' | 'ADMIN' })}>
                      <option value="USUARIO">Usuario</option><option value="ADMIN">Administrador</option>
                    </select>
                  </td>
                  <td>{u.activo ? <span className="chip chip--ok">Activo</span> : <span className="chip chip--gris">Sin acceso</span>}</td>
                  <td className="numeros">{u.ultimoIngreso ? fecha(u.ultimoIngreso) : <span className="tenue">Nunca</span>}</td>
                  <td>{u.creadoPor ?? <span className="tenue">Inicial</span>}</td>
                  <td>{u.id !== usuario.id && (
                    <button type="button" className={`boton-texto${u.activo ? ' boton-texto--peligro' : ''}`} onClick={() => cambiar(u, { activo: !u.activo })}>
                      {u.activo ? 'Quitar acceso' : 'Devolver acceso'}
                    </button>
                  )}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="tarjeta">
        <h2>Actividad reciente</h2>
        <div className="tabla-caja" style={{ maxHeight: 420, overflowY: 'auto' }}>
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Quién</th><th>Qué hizo</th><th>Detalle</th></tr></thead>
            <tbody>
              {actividad.map((a) => (
                <tr key={a.id}>
                  <td className="numeros">{fecha(a.fecha)}</td>
                  <td>{a.email ?? '—'}</td>
                  <td>{ACCIONES[a.accion] ?? a.accion}</td>
                  <td className="suave">{resumen(a)}</td>
                </tr>
              ))}
              {!actividad.length && <tr><td colSpan={4} className="tenue">Sin actividad todavía.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
