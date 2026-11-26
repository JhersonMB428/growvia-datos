import { useEffect, useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { api, avisarSesionVencida, type Usuario } from './api';
import { SesionContexto } from './sesion';
import { Entrar } from './paginas/Entrar';
import { Bases } from './paginas/Bases';
import { Base } from './paginas/Base';
import { Accesos } from './paginas/Accesos';
import { Consumo } from './paginas/Consumo';

export function App() {
  const [usuario, setUsuario] = useState<Usuario | null | undefined>(undefined);

  useEffect(() => {
    avisarSesionVencida(() => setUsuario(null));
    api<Usuario>('/auth/yo').then(setUsuario).catch(() => setUsuario(null));
  }, []);

  async function salir() {
    await api('/auth/salir', { metodo: 'POST' }).catch(() => undefined);
    setUsuario(null);
  }

  if (usuario === undefined) return <div className="ingreso" aria-busy="true" />;
  if (!usuario) return <Entrar onEntrar={setUsuario} />;

  const admin = usuario.rol === 'ADMIN';
  return (
    <SesionContexto.Provider value={{ usuario, salir }}>
      <header className="barra">
        <NavLink to="/" className="barra__marca" aria-label="Growvia Datos, inicio">
          <img src="/img/logo-growvia.webp" alt="" /> <span>Datos</span>
        </NavLink>
        <nav aria-label="Menú">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'activo' : '')}>Bases</NavLink>
          <NavLink to="/consumo" className={({ isActive }) => (isActive ? 'activo' : '')}>Consumo</NavLink>
          {admin && <NavLink to="/accesos" className={({ isActive }) => (isActive ? 'activo' : '')}>Accesos</NavLink>}
        </nav>
        <div className="barra__usuario">
          <span>{usuario.nombre || usuario.email}{admin ? ' · Admin' : ''}</span>
          <button type="button" className="boton-texto" onClick={salir}>Salir</button>
        </div>
      </header>
      <main className="contenido">
        <Routes>
          <Route path="/" element={<Bases />} />
          <Route path="/bases/:id" element={<Base />} />
          <Route path="/consumo" element={<Consumo />} />
          <Route path="/accesos" element={admin ? <Accesos /> : <Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </SesionContexto.Provider>
  );
}
