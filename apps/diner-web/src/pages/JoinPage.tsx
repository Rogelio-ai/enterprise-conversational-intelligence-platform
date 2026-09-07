import { type FormEvent, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import { LoadingState } from '../components/LoadingState';
import { ThemeButton } from '../components/ThemeButton';
import { useAuth } from '../session/AuthContext';

interface Fields {
  displayName: string;
  email: string;
  accessCode: string;
}

type FieldErrors = Partial<Record<keyof Fields, string>>;

function validate(fields: Fields): FieldErrors {
  const errors: FieldErrors = {};
  if (!fields.displayName.trim()) errors.displayName = 'Escribe tu nombre para continuar.';
  if (fields.displayName.trim().length > 200) errors.displayName = 'El nombre es demasiado largo.';
  if (fields.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) errors.email = 'Revisa que el email tenga un formato válido.';
  if (fields.email.length > 320) errors.email = 'El email es demasiado largo.';
  if (!/^\d{4}$/.test(fields.accessCode)) errors.accessCode = 'Ingresa los cuatro dígitos del código.';
  return errors;
}

function joinErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Ocurrió algo inesperado. Intenta nuevamente.';
  if (error.status === 0) return 'No pudimos conectar con el restaurante. Revisa tu conexión e intenta de nuevo.';
  if (error.status === 401) return 'El código o el acceso de esta mesa no son válidos. Verifícalos e intenta de nuevo.';
  if (error.status === 429) return 'Se hicieron varios intentos. Espera un momento antes de volver a intentar.';
  if (error.status === 409) return 'No pudimos completar el acceso a esta mesa. Pide ayuda al personal del restaurante.';
  if (error.status === 422) return 'Revisa tus datos y vuelve a intentar.';
  return 'El restaurante no pudo completar tu acceso. Intenta nuevamente.';
}

export function JoinPage() {
  const { joinContextKey: routeContext } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { status, authenticate } = useAuth();
  const [fields, setFields] = useState<Fields>({ displayName: '', email: '', accessCode: '' });
  const [errors, setErrors] = useState<FieldErrors>({});

  const joinContextKey = useMemo(
    () => routeContext || searchParams.get('join_context_key') || searchParams.get('context') || '',
    [routeContext, searchParams],
  );
  const hasValidContext = joinContextKey.length >= 32 && joinContextKey.length <= 64;

  const mutation = useMutation({
    mutationFn: dinerApi.join,
    onSuccess: (response) => {
      authenticate(response);
      navigate('/app', { replace: true });
    },
  });

  if (status === 'checking') return <LoadingState message="Comprobando tu acceso…" />;
  if (status === 'authenticated') return <Navigate to="/app" replace />;

  const update = (field: keyof Fields, value: string) => {
    if (mutation.error) mutation.reset();
    setFields((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validate(fields);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length || !hasValidContext) return;
    mutation.mutate({
      join_context_key: joinContextKey,
      display_name: fields.displayName.trim(),
      ...(fields.email.trim() ? { email: fields.email.trim() } : {}),
      access_code: fields.accessCode,
    });
  };

  return (
    <main className="join-layout">
      <section className="brand-panel" aria-label="Bienvenida">
        <div className="brand-topline">
          <a className="wordmark" href="/" aria-label="Mesa, inicio">
            <span className="wordmark-mark" aria-hidden="true">M</span>
            <span>Mesa</span>
          </a>
          <ThemeButton />
        </div>
        <div className="brand-message">
          <p className="eyebrow">Tu mesa, a tu manera</p>
          <h1>Una gran experiencia empieza aquí.</h1>
          <p>Entra de forma segura y disfruta el restaurante desde tu mesa.</p>
        </div>
        <div className="table-scene" aria-hidden="true">
          <span className="plate"><i /></span>
          <span className="glass" />
          <span className="leaf leaf--one" />
          <span className="leaf leaf--two" />
        </div>
        <p className="brand-footnote">Acceso privado · Conexión segura</p>
      </section>

      <section className="form-panel">
        <div className="mobile-topline">
          <a className="wordmark" href="/" aria-label="Mesa, inicio">
            <span className="wordmark-mark" aria-hidden="true">M</span><span>Mesa</span>
          </a>
          <ThemeButton />
        </div>
        <div className="access-card">
          <div className="access-heading">
            <p className="eyebrow">Bienvenido</p>
            <h2>Únete a tu mesa</h2>
            <p>Usa el código que te compartió el restaurante.</p>
          </div>

          {!hasValidContext ? (
            <div className="context-error" role="alert">
              <span aria-hidden="true">!</span>
              <div>
                <h3>Falta el acceso de la mesa</h3>
                <p>Escanea nuevamente el código QR de tu mesa o solicita ayuda al personal.</p>
              </div>
            </div>
          ) : (
            <form onSubmit={submit} noValidate>
              <div className="field">
                <label htmlFor="display-name">Nombre</label>
                <input id="display-name" name="name" autoComplete="name" maxLength={200} value={fields.displayName} onChange={(event) => update('displayName', event.target.value)} aria-invalid={Boolean(errors.displayName)} aria-describedby={errors.displayName ? 'display-name-error' : undefined} placeholder="¿Cómo te llamas?" autoFocus />
                {errors.displayName && <p className="field-error" id="display-name-error">{errors.displayName}</p>}
              </div>

              <div className="field">
                <label htmlFor="email">Email <span>(opcional)</span></label>
                <input id="email" name="email" type="email" inputMode="email" autoComplete="email" maxLength={320} value={fields.email} onChange={(event) => update('email', event.target.value)} aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? 'email-error' : 'email-help'} placeholder="tu@email.com" />
                <p className="field-help" id="email-help">Para reconocerte en una próxima visita.</p>
                {errors.email && <p className="field-error" id="email-error">{errors.email}</p>}
              </div>

              <div className="field">
                <label htmlFor="access-code">Código de acceso</label>
                <input className="code-input" id="access-code" name="one-time-code" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{4}" maxLength={4} value={fields.accessCode} onChange={(event) => update('accessCode', event.target.value.replace(/\D/g, '').slice(0, 4))} aria-invalid={Boolean(errors.accessCode)} aria-describedby={errors.accessCode ? 'access-code-error' : 'access-code-help'} placeholder="0000" />
                <p className="field-help" id="access-code-help">Código de 4 dígitos.</p>
                {errors.accessCode && <p className="field-error" id="access-code-error">{errors.accessCode}</p>}
              </div>

              {mutation.error && <div className="form-error" role="alert"><span aria-hidden="true">!</span><p>{joinErrorMessage(mutation.error)}</p></div>}

              <button className="primary-button" type="submit" disabled={mutation.isPending}>
                {mutation.isPending && <span className="spinner" aria-hidden="true" />}
                <span>{mutation.isPending ? 'Entrando…' : 'Entrar'}</span>
              </button>
              <p className="privacy-note">Tu información se usa únicamente para atenderte durante tu visita.</p>
            </form>
          )}
        </div>
      </section>
    </main>
  );
}
