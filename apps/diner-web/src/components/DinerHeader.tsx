import { NavLink } from 'react-router-dom';
import { ThemeButton } from './ThemeButton';

export function DinerHeader() {
  return (
    <header className="app-header">
      <NavLink className="wordmark" to="/app" aria-label="Mesa, inicio">
        <span className="wordmark-mark" aria-hidden="true">M</span>
        <span>Mesa</span>
      </NavLink>
      <div className="app-header-actions">
        <nav className="primary-nav" aria-label="Navegación principal">
          <NavLink to="/app" end>Inicio</NavLink>
          <NavLink to="/menu">Menú</NavLink>
        </nav>
        <ThemeButton />
      </div>
    </header>
  );
}
