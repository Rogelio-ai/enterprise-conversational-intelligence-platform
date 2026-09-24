import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ApiError } from '../api/client';
import { ThemeButton } from '../components/ThemeButton';
import { useAuth } from '../session/AuthContext';

export function LoginPage() {
  const { status, login } = useAuth();
  const location = useLocation();
  const [error, setError] = useState<{ kind: 'rejected' | 'network' | 'other'; message: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const usernameRef = useRef<HTMLInputElement>(null);
  useEffect(() => { if (error) usernameRef.current?.focus(); }, [error]);

  if (status === 'authenticated' || status === 'checking' || status === 'restoration-error') {
    const destination = typeof location.state === 'object' && location.state && 'from' in location.state
      ? String(location.state.from)
      : '/';
    return <Navigate to={destination} replace />;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    const data = new FormData(event.currentTarget);
    try {
      await login({
        username: String(data.get('username') ?? '').trim(),
        password: String(data.get('password') ?? ''),
      });
    } catch (reason) {
      if (reason instanceof ApiError && reason.kind === 'network') {
        setError({ kind: 'network', message: 'No pudimos contactar al servicio. Revisa tu conexión e inténtalo de nuevo.' });
      } else if (reason instanceof ApiError && reason.status === 409 && reason.code === 'staff_already_logged_in') {
        setError({ kind: 'other', message: 'Ya tienes una sesión activa. Cierra tu sesión actual antes de iniciar otra.' });
      } else if (reason instanceof ApiError && reason.kind === 'authentication') {
        setError({ kind: 'rejected', message: 'El usuario o la contraseña no son válidos.' });
      } else {
        setError({ kind: 'other', message: reason instanceof Error ? reason.message : 'No pudimos iniciar sesión.' });
      }
    } finally { setSubmitting(false); }
  }

  return (
    <main className="login-layout">
      <section className="login-brand" aria-label="ECIP Staff">
        <div className="brand-mark" aria-hidden="true">E</div>
        <div>
          <p className="eyebrow">Inteligencia para restaurantes</p>
          <h1>La operación,<br />en un solo lugar.</h1>
          <p>Contexto claro. Acciones seguras. Ritmo de servicio.</p>
        </div>
        <p className="brand-foot">ECIP · Staff</p>
      </section>
      <section className="login-form-panel">
        <div className="login-topline">
          <a className="wordmark" href="/login" aria-label="ECIP Staff, inicio de sesión"><span>E</span>ECIP Staff</a>
          <ThemeButton />
        </div>
        <form className="login-card" onSubmit={submit} aria-describedby={error ? 'login-error' : undefined}>
          <div className="login-heading">
            <p className="eyebrow">Acceso de personal</p>
            <h2>Bienvenido de vuelta</h2>
            <p>Ingresa con las credenciales asignadas por tu restaurante.</p>
          </div>
          {status === 'expired' ? <div className="notice" role="status"><strong>Tu sesión terminó.</strong> Vuelve a ingresar para continuar.</div> : null}
          {error ? <div id="login-error" className={`notice notice--${error.kind}`} role="alert"><strong>{error.kind === 'network' ? 'Sin conexión' : error.kind === 'rejected' ? 'Acceso rechazado' : 'No se pudo ingresar'}</strong>{error.message}</div> : null}
          <label className="field">
            <span>Usuario</span>
            <input ref={usernameRef} name="username" type="text" autoComplete="username" required maxLength={64} />
          </label>
          <label className="field">
            <span>Contraseña</span>
            <input name="password" type="password" autoComplete="current-password" required maxLength={128} />
          </label>
          <button className="primary-button" type="submit" disabled={submitting}>{submitting ? 'Comprobando acceso…' : 'Ingresar a operación'}</button>
          <p className="security-note"><span aria-hidden="true">◆</span> Acceso protegido y limitado por tus permisos.</p>
        </form>
      </section>
    </main>
  );
}
