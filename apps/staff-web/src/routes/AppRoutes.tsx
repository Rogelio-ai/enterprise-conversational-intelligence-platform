import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { StaffShell } from '../components/StaffShell';
import { StatePanel } from '../components/StatePanel';
import { StaffContextProvider, useStaffContext } from '../context/StaffContext';
import { canUseWorkspace, workspaces, type Workspace } from '../navigation/workspaces';
import { LoginPage } from '../pages/LoginPage';
import { StaffHomePage } from '../pages/StaffHomePage';
import { HostPage } from '../pages/HostPage';
import { KitchenPage } from '../pages/KitchenPage';
import { WaiterPage } from '../pages/WaiterPage';
import { CashierPage } from '../pages/CashierPage';
import { WorkspacePlaceholder } from '../pages/WorkspacePlaceholder';
import { useAuth } from '../session/AuthContext';

function AuthenticatedBoundary({ children }: { children: ReactNode }) {
  const { status, retryRestoration, logout } = useAuth();
  const location = useLocation();
  if (status === 'checking') return <StatePanel eyebrow="Acceso protegido" title="Comprobando tu sesión…" icon="◌"><p>Estamos recuperando tu identidad y permisos actuales.</p></StatePanel>;
  if (status === 'restoration-error') return <StatePanel eyebrow="Conexión interrumpida" title="Tu sesión sigue guardada" icon="↻"><p>No pudimos comprobarla temporalmente. No cerramos tu acceso por un problema de red.</p><div className="state-actions"><button className="primary-button" onClick={retryRestoration}>Reintentar</button><button className="secondary-button" onClick={logout}>Salir</button></div></StatePanel>;
  if (status !== 'authenticated') return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <StaffContextProvider>{children}</StaffContextProvider>;
}

function LocationBoundary({ children }: { children: ReactNode }) {
  const context = useStaffContext();
  if (context.status === 'loading') return <StatePanel eyebrow="Contexto operativo" title="Cargando ubicaciones…" icon="◌"><p>Validamos tu alcance directamente con el backend.</p></StatePanel>;
  if (context.status === 'error') return <StatePanel eyebrow="Conexión interrumpida" title="No pudimos cargar tus ubicaciones" icon="↻"><p>Tu sesión permanece activa. Intenta recuperar el contexto.</p><button className="primary-button" onClick={context.retry}>Reintentar</button></StatePanel>;
  if (context.status === 'selection-required') return <StatePanel eyebrow="Contexto requerido" title="Elige dónde operar" icon="⌖"><p>Tu cuenta tiene acceso tenant-wide a más de una ubicación. La selección define el contexto de esta sesión.</p><div className="location-choices">{context.locations.map((location) => <button className="location-choice" type="button" onClick={() => context.selectLocation(location.id)} key={location.id}><strong>{location.name}</strong><span>{location.code} · {location.timezone}</span></button>)}</div></StatePanel>;
  if (context.status === 'unavailable') return <StatePanel eyebrow="Contexto no disponible" title="No hay una ubicación operable" icon="!"><p>Tu cuenta no tiene `location.read` o el tenant no contiene ubicaciones activas. Solicita al administrador revisar tus permisos.</p></StatePanel>;
  return <StaffShell>{children}</StaffShell>;
}

function WorkspaceBoundary({ workspace, children }: { workspace: Workspace; children?: ReactNode }) {
  const { identity } = useAuth();
  if (!canUseWorkspace(identity?.permissions ?? [], workspace)) {
    return <StatePanel eyebrow="Acceso restringido" title="Este espacio no está disponible" icon="×"><p>Tu identidad no reúne las capacidades requeridas. La autorización permanece en el backend.</p><a className="secondary-button button-link" href="/">Volver al inicio</a></StatePanel>;
  }
  return children ?? <WorkspacePlaceholder workspace={workspace} />;
}

function ProtectedApp({ children }: { children: ReactNode }) {
  return <AuthenticatedBoundary><LocationBoundary>{children}</LocationBoundary></AuthenticatedBoundary>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedApp><StaffHomePage /></ProtectedApp>} />
      {workspaces.map((workspace) => (
        <Route key={workspace.key} path={workspace.path} element={
          <ProtectedApp>
            <WorkspaceBoundary workspace={workspace}>
              {workspace.key === 'host' ? <HostPage />
                : workspace.key === 'waiter' ? <WaiterPage />
                  : workspace.key === 'kitchen' ? <KitchenPage />
                    : workspace.key === 'cashier' ? <CashierPage /> : undefined}
            </WorkspaceBoundary>
          </ProtectedApp>
        } />
      ))}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
