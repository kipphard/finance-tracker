import type { ReactNode } from "react";

export function Card({
  title,
  action,
  wide,
  children,
}: {
  title: string;
  action?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={"card" + (wide ? " span-2" : "")}>
      <header className="card__head">
        <h2>{title}</h2>
        {action}
      </header>
      <div className="card__body">{children}</div>
    </section>
  );
}
