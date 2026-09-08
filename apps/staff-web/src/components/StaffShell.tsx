import type { PropsWithChildren } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useStaffContext } from '../context/StaffContext';
import { canUseWorkspace, workspaces } from '../navigation/workspaces';
import { useAuth } from '../session/AuthContext';
import { ThemeButton } from './ThemeButton';

export function StaffShell({ children }: PropsWithChildren) {
  const { identity, logout } = useAuth();
  const { tenant, organization, location, locations, selectLocation } = useStaffContext();
  const available = workspaces.filter((workspace) => canUseWorkspace(identity?.permissions ?? [], workspace));
  return (
    <div className="staff-app">
      <header className="shell-header">
        <Link className="wordmark" to="/" aria-label="ECIP Staff, inicio"><span>E</span>ECIP <b>Staff</b></Link>
        <div className="context-strip" aria-label="Contexto operativo actual">
          <div><small>Tenant</small><strong>{tenant?.name ?? `#${identity?.tenant_id}`}</strong></div>
          <span className="context-divider" aria-hidden="true"></span>
          <div><small>Organización</small><strong>{organization?.name ?? (location ? `#${location.organization_id}` : 'Pendiente')}</strong></div>
          <span className="context-divider" aria-hidden="true"></span>
          <label>
            <span>Ubicación</span>
            {locations.length > 1 ? (
              <select aria-label="Ubicación operativa" value={location?.id ?? ''} onChange={(event) => selectLocation(Number(event.target.value))}>
                <option value="" disabled>Seleccionar</option>
                {locations.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
              </select>
            ) : <strong>{location?.name ?? 'Pendiente'}</strong>}
          </label>
        </div>
        <div className="shell-actions">
          <ThemeButton />
          <div className="user-menu">
            <span className="user-avatar" aria-hidden="true">{identity?.display_name.trim().charAt(0).toUpperCase() || 'U'}</span>
            <div><strong>{identity?.display_name}</strong><small>{identity?.roles.join(' · ') || 'Personal'}</small></div>
          </div>
          <button className="logout-button" type="button" onClick={logout}>Salir</button>
        </div>
      </header>
      <div className="shell-body">
        <aside className="shell-sidebar">
          <nav aria-label="Espacios de trabajo">
            <NavLink to="/" end><span aria-hidden="true">⌂</span>Inicio</NavLink>
            {available.map((workspace) => <NavLink to={workspace.path} key={workspace.key}><span aria-hidden="true">◇</span>{workspace.label}</NavLink>)}
          </nav>
          <p><span aria-hidden="true"></span>Sesión protegida</p>
        </aside>
        <main className="shell-content" id="main-content">{children}</main>
      </div>
    </div>
  );
}
