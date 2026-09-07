import type { ReactNode } from 'react';

export function StateMessage({ eyebrow, title, children, action }: { eyebrow: string; title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <main className="state-page state-page--card">
      <div className="state-mark" aria-hidden="true">✦</div>
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <div className="state-copy">{children}</div>
      {action && <div className="state-action">{action}</div>}
    </main>
  );
}
