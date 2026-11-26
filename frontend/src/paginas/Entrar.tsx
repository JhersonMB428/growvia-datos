import { useState, type FormEvent } from 'react';
import { api, textoError, type Usuario } from '../api';

export function Entrar({ onEntrar }: { onEntrar: (u: Usuario) => void }) {
  const [email, setEmail] = useState('');
  const [codigo, setCodigo] = useState('');
  const [paso, setPaso] = useState<'correo' | 'codigo'>('correo');
  const [mensaje, setMensaje] = useState('');
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);

  async function pedir(e?: FormEvent) {
    e?.preventDefault();
    setError(''); setOcupado(true);
    try {
      const r = await api<{ mensaje: string }>('/auth/codigo', { cuerpo: { email } });
      setMensaje(r.mensaje); setPaso('codigo'); setCodigo('');
    } catch (err) { setError(textoError(err)); }
    finally { setOcupado(false); }
  }

  async function verificar(e: FormEvent) {
    e.preventDefault();
    setError(''); setOcupado(true);
    try {
      const r = await api<{ usuario: Usuario }>('/auth/verificar', { cuerpo: { email, codigo } });
      onEntrar(r.usuario);
    } catch (err) { setError(textoError(err)); }
    finally { setOcupado(false); }
  }

  return (
    <div className="ingreso">
      <div className="ingreso__tarjeta">
        <div className="ingreso__marca"><img src="/img/logo-growvia.webp" alt="Growvia" /> Datos</div>
        <div>
          <h1 style={{ fontSize: 22 }}>{paso === 'correo' ? 'Entrar' : 'Revisa tu correo'}</h1>
          <p className="suave" style={{ marginTop: 6 }}>
            {paso === 'correo' ? 'Completa bases de empresas con datos de SUNAT antes de subirlas al CRM.' : mensaje}
          </p>
        </div>
        {paso === 'correo' ? (
          <form onSubmit={pedir} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="campo">
              <label className="etiqueta" htmlFor="email">Correo de trabajo</label>
              <input id="email" className="entrada" type="email" autoComplete="email" autoFocus required value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="nombre@corevia.global" />
            </div>
            {error && <div className="alerta" role="alert">{error}</div>}
            <button className="boton" disabled={ocupado || !email.includes('@')}>{ocupado ? 'Enviando…' : 'Enviarme un código'}</button>
          </form>
        ) : (
          <form onSubmit={verificar} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="campo">
              <label className="etiqueta" htmlFor="codigo">Código de 6 dígitos enviado a {email}</label>
              <input id="codigo" className="entrada entrada--codigo numeros" inputMode="numeric" autoComplete="one-time-code" autoFocus maxLength={6}
                value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))} />
            </div>
            {error && <div className="alerta" role="alert">{error}</div>}
            <button className="boton" disabled={ocupado || codigo.length !== 6}>{ocupado ? 'Verificando…' : 'Entrar'}</button>
            <div className="fila fila--entre">
              <button type="button" className="boton-texto" onClick={() => { setPaso('correo'); setError(''); }}>Cambiar correo</button>
              <button type="button" className="boton-texto" onClick={() => pedir()} disabled={ocupado}>Enviar otro código</button>
            </div>
          </form>
        )}
        <p className="tenue" style={{ fontSize: 13 }}>¿No tienes acceso? Pídeselo a un administrador.</p>
      </div>
    </div>
  );
}
