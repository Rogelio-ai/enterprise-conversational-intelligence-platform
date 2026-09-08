import { Link } from 'react-router-dom';
import type { Workspace } from '../navigation/workspaces';

export function WorkspacePlaceholder({ workspace }: { workspace: Workspace }) {
  return (
    <section className="placeholder-page">
      <p className="eyebrow">Espacio autorizado</p>
      <h1>{workspace.label}</h1>
      <p>La base de acceso está lista. Las herramientas de {workspace.description.toLocaleLowerCase()} se habilitarán en su slice operativo.</p>
      <div className="placeholder-boundary"><span aria-hidden="true">◇</span><div><strong>Fundación verificada</strong><p>Sin acciones operativas en WS-31-B1.</p></div></div>
      <Link className="secondary-button" to="/">Volver al inicio</Link>
    </section>
  );
}
