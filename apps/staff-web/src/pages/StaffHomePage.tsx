import { Link } from 'react-router-dom';
import { useAuth } from '../session/AuthContext';
import { useStaffContext } from '../context/StaffContext';
import { canUseWorkspace, workspaces } from '../navigation/workspaces';

export function StaffHomePage() {
  const { identity } = useAuth();
  const { location } = useStaffContext();
  const available = workspaces.filter((workspace) => canUseWorkspace(identity?.permissions ?? [], workspace));
  return (
    <div className="home-page">
      <header className="home-hero">
        <div>
          <p className="eyebrow">Centro de operación</p>
          <h1>Todo en contexto.</h1>
          <p>{location ? `Estás operando en ${location.name}.` : 'Selecciona una ubicación para comenzar.'} Aquí sólo aparecen las áreas autorizadas para tu cuenta.</p>
        </div>
        <div className="status-orbit" aria-label="Estado del contexto: conectado">
          <span aria-hidden="true"></span>
          Contexto conectado
        </div>
      </header>
      <section aria-labelledby="workspace-heading">
        <div className="section-heading">
          <div><p className="eyebrow">Tus capacidades</p><h2 id="workspace-heading">Espacios disponibles</h2></div>
          <p>{available.length} {available.length === 1 ? 'espacio habilitado' : 'espacios habilitados'}</p>
        </div>
        {available.length ? (
          <div className="workspace-grid">
            {available.map((workspace, index) => (
              <Link className="workspace-card" to={workspace.path} key={workspace.key}>
                <span className="workspace-index">0{index + 1}</span>
                <div><h3>{workspace.label}</h3><p>{workspace.description}</p></div>
                <span className="workspace-arrow" aria-hidden="true">→</span>
              </Link>
            ))}
          </div>
        ) : <div className="empty-panel"><strong>Sin espacios asignados</strong><p>Tu identidad está activa, pero aún no tiene un conjunto completo de permisos operativos.</p></div>}
      </section>
      <section className="identity-summary" aria-labelledby="identity-heading">
        <div><p className="eyebrow">Identidad activa</p><h2 id="identity-heading">{identity?.display_name}</h2></div>
        <dl>
          <div><dt>Roles</dt><dd>{identity?.roles.length ? identity.roles.join(', ') : 'Sin rol nominal'}</dd></div>
          <div><dt>Capacidades</dt><dd>{identity?.permissions.length ?? 0} autorizadas</dd></div>
          <div><dt>Membresía</dt><dd>#{identity?.membership_id}</dd></div>
        </dl>
      </section>
    </div>
  );
}
