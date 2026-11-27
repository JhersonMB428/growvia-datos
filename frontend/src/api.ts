export class ErrorApi extends Error {
  estado: number;
  constructor(estado: number, mensaje: string) { super(mensaje); this.estado = estado; }
}

let alVencer: () => void = () => undefined;
export const avisarSesionVencida = (f: () => void) => { alVencer = f; };

export async function api<T>(ruta: string, opciones: { metodo?: string; cuerpo?: unknown; formulario?: FormData } = {}): Promise<T> {
  const r = await fetch(`/api${ruta}`, {
    method: opciones.metodo ?? (opciones.cuerpo || opciones.formulario ? 'POST' : 'GET'),
    credentials: 'same-origin',
    headers: opciones.cuerpo !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: opciones.formulario ?? (opciones.cuerpo !== undefined ? JSON.stringify(opciones.cuerpo) : undefined),
  });
  if (!r.ok) {
    let mensaje = 'No se pudo completar la acción';
    try {
      const d = await r.json();
      mensaje = typeof d.detail === 'string' ? d.detail : Array.isArray(d.detail) ? 'Revisa los datos' : mensaje;
    } catch { /* sin cuerpo */ }
    if (r.status === 401 && !ruta.startsWith('/auth/')) alVencer();
    throw new ErrorApi(r.status, mensaje);
  }
  return r.json() as Promise<T>;
}

export const textoError = (e: unknown) => (e instanceof ErrorApi ? e.message : 'No hay conexión. Inténtalo de nuevo.');

// ───────── Tipos ─────────
export type Usuario = { id: number; email: string; nombre: string; rol: 'ADMIN' | 'USUARIO' };
export type EstadoTrabajo = 'CARGADO' | 'BUSCANDO_RUC' | 'REVISAR_RUC' | 'CONSULTANDO' | 'REVISION' | 'ERROR';
export type EstadoRuc = 'DEL_ARCHIVO' | 'EXACTO' | 'PROBABLE' | 'VARIOS' | 'NO_ENCONTRADO' | 'INVALIDO' | 'ELEGIDO' | 'COINCIDENCIA' | 'DESCARTADA';
export type Persona = { nombre: string; cargo: string; dni: string; telefono: string; correo: string };

export type TrabajoResumen = {
  id: string; nombre: string; archivo: string; estado: EstadoTrabajo; mensaje: string | null; progreso: number; total: number;
  descargas: number; creadoAt: string; creadoPor: string; filas: number; conRuc: number; porRevisar: number; consultadas: number;
};
export type OpcionRuc = { ruc: string; razon: string; estado: string; condicion: string; ubigeo: string; direccion: string };
export type Representante = { nombre: string; dni: string; cargo: string; desde: string; documento: string; tipo: string };
export type Final = {
  ruc: string; razon: string; representante: string; dni: string; cargo: string; telefono: string; correo: string;
  departamento: string; provincia: string; distrito: string; lineas: number | null; operador: string; lineas_por: Record<string, number>;
  segmento: string; segmento_estimado: string; trabajadores: number | null; periodo: string; estado_sunat: string; activo: boolean;
  otros_telefonos: string[]; otros_correos: string[]; otros_contactos: Persona[]; direccion: string; nombre_archivo: string; tipo: string; como_ruc: string; observacion: string;
};
export type Fila = {
  id: number; n: number; rucEstado: EstadoRuc; opciones: OpcionRuc[]; consultada: boolean; representantes: Representante[];
  datos: Record<string, unknown>; original: Record<string, string>; final: Final; faltan: string[];
};
export type Trabajo = {
  id: string; nombre: string; archivo: string; estado: EstadoTrabajo; progreso: number; total: number; mensaje: string | null;
  columnasExtra: string[]; endpoints: string[]; descargas: number; creadoAt: string; creadoPor: string; creadoPorId: number; filas: Fila[];
};
export type Estimado = { empresas: number; consultas: number; usadasMes: number; limiteMes: number; quedan: number; alcanza: boolean; tokenActivo: boolean };
export type Consumo = {
  usadasMes: number; limiteMes: number; tokenActivo: boolean;
  porDia: { dia: string; pagadas: number; reutilizadas: number }[];
  porEndpoint: { endpoint: string; pagadas: number }[];
  porUsuario: { email: string | null; pagadas: number; reutilizadas: number }[];
  padron: { descargado?: string; tamano?: number };
};
export type UsuarioAcceso = Usuario & { activo: boolean; creadoAt: string; ultimoIngreso: string | null; creadoPor: string | null };
export type Actividad = { id: number; accion: string; detalle: Record<string, unknown> | null; fecha: string; email: string | null };

export const fecha = (iso: string | null | undefined, conHora = true) =>
  iso ? new Date(iso).toLocaleString('es-PE', { day: '2-digit', month: 'short', year: 'numeric', ...(conHora ? { hour: '2-digit', minute: '2-digit' } : {}) }) : '—';
