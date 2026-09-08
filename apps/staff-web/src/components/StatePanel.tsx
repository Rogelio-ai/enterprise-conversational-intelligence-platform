import type { PropsWithChildren, ReactNode } from 'react';

export function StatePanel({ eyebrow, title, children, icon }: PropsWithChildren<{
  eyebrow: string;
  title: string;
  icon?: ReactNode;
}>) {
  return (
    <div className="state-layout">
      <section className="state-panel" aria-live="polite">
        {icon ? <div className="state-icon" aria-hidden="true">{icon}</div> : null}
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <div className="state-copy">{children}</div>
      </section>
    </div>
  );
}
