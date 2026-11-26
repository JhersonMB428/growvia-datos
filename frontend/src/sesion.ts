import { createContext, useContext } from 'react';
import type { Usuario } from './api';

export const SesionContexto = createContext<{ usuario: Usuario; salir: () => void } | null>(null);

export function useSesion() {
  const s = useContext(SesionContexto);
  if (!s) throw new Error('Sin sesión');
  return s;
}
