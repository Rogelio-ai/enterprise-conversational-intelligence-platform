import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { DinerHeader } from '../components/DinerHeader';
import { useAuth } from '../session/AuthContext';

export function DinerHomePage() {
  const { session } = useAuth();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = 'Inicio · Mesa';
    heading.current?.focus();
  }, []);

  return (
    <div className="shell">
      <DinerHeader />
      <main className="shell-content">
        <div className="welcome-orbit" aria-hidden="true"><span>✦</span></div>
        <p className="eyebrow">Ya estás en tu mesa</p>
        <h1 ref={heading} tabIndex={-1}>Hola, {session?.displayName}</h1>
        <p>Tu acceso está listo. Explora la carta preparada para tu mesa.</p>
        <div className="session-confirmation" role="status">
          <span aria-hidden="true">✓</span>
          <div><strong>Sesión activa</strong><small>Conectado de forma segura</small></div>
        </div>
        <Link className="primary-button home-menu-action" to="/menu">Ver el menú <span aria-hidden="true">→</span></Link>
      </main>
      <footer className="shell-footer"><span>Experiencia para comensales</span><span aria-hidden="true">✦</span></footer>
    </div>
  );
}
