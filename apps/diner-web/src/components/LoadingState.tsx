export function LoadingState({ message = 'Preparando tu experiencia…' }: { message?: string }) {
  return (
    <div className="state-page" role="status" aria-live="polite">
      <span className="spinner spinner--large" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}
