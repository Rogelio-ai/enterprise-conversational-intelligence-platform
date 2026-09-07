import { useEffect, useRef } from 'react';
import { ThemeButton } from '../components/ThemeButton';
import { useAuth } from '../session/AuthContext';

export function DinerHomePage() {
  const { session } = useAuth();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);

  return (
    <div className="shell">
      <header className="shell-header">
        <a className="wordmark" href="/app" aria-label="Mesa, inicio">
          <span className="wordmark-mark" aria-hidden="true">M</span><span>Mesa</span>
        </a>
        <ThemeButton />
      </header>
      <main className="shell-content">
        <div className="welcome-orbit" aria-hidden="true"><span>✦</span></div>
        <p className="eyebrow">Ya estás en tu mesa</p>
        <h1 ref={heading} tabIndex={-1}>Hola, {session?.displayName}</h1>
        <p>Tu acceso está listo. En un momento podrás comenzar a explorar la experiencia del restaurante.</p>
        <div className="session-confirmation" role="status">
          <span aria-hidden="true">✓</span>
          <div><strong>Sesión activa</strong><small>Conectado de forma segura</small></div>
        </div>
      </main>
      <footer className="shell-footer"><span>Experiencia para comensales</span><span aria-hidden="true">✦</span></footer>
    </div>
  );
}
