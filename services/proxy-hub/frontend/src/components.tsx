import type { FormEvent, ReactNode } from "react";

import { statusLabel, useI18n } from "./i18n";

export function navigate(path: string): void {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <header className="page-header">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action ? (
        <button className="primary-button" onClick={action.onClick}>
          {action.label}
        </button>
      ) : null}
    </header>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "blue" | "amber";
}) {
  return (
    <article className="metric-card">
      <div className={`metric-dot ${tone}`} />
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

export function StatusPill({ status }: { status: string }) {
  const { t } = useI18n();
  const active =
    status === "active" || status === "ready" || status === "forwarded";
  return (
    <span className={active ? "status active" : "status disabled"}>
      <i />
      {statusLabel(status, t)}
    </span>
  );
}

export function EmptyState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">◇</div>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}

export function InlineAlert({
  message,
  requestId,
}: {
  message: string;
  requestId?: string | null;
}) {
  return (
    <div className="inline-alert">
      {message}
      {requestId ? <code>Request {requestId}</code> : null}
    </div>
  );
}

export function ServerNotice({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  return (
    <div className="server-notice" role="status">
      <span>{message}</span>
      <button aria-label="Dismiss server response" onClick={onClose}>
        ×
      </button>
    </div>
  );
}

export function PanelState({
  kind,
  message,
  requestId,
  onRetry,
}: {
  kind: "loading" | "empty" | "denied" | "unavailable";
  message?: string;
  requestId?: string | null;
  onRetry?: () => void;
}) {
  const { t } = useI18n();
  if (kind === "loading") {
    return <div className="panel-state loading-lines">{t("Loading server data…")}</div>;
  }
  if (kind === "empty") {
    return (
      <EmptyState title={t("No records")} message={message ?? t("Nothing to show.")} />
    );
  }
  return (
    <div className="panel-state">
      <h3>{kind === "denied" ? t("Access denied") : t("Service unavailable")}</h3>
      <p>{message}</p>
      {requestId ? <code>{t("Request")} {requestId}</code> : null}
      {onRetry ? (
        <button className="secondary-button" onClick={onRetry}>
          {t("Retry")}
        </button>
      ) : null}
    </div>
  );
}

export function CenteredState({
  title,
  message,
  requestId,
  pulse = false,
  action,
}: {
  title: string;
  message?: string;
  requestId?: string | null;
  pulse?: boolean;
  action?: { label: string; href?: string; onClick?: () => void };
}) {
  return (
    <main className="centered-state">
      <div className={pulse ? "state-mark pulse" : "state-mark"}>S</div>
      <span className="eyebrow">Scholar Proxy Hub</span>
      <h1>{title}</h1>
      {message ? <p>{message}</p> : null}
      {requestId ? <code>Request {requestId}</code> : null}
      {action?.href ? (
        <a className="primary-button" href={action.href}>
          {action.label}
        </a>
      ) : action?.onClick ? (
        <button className="primary-button" onClick={action.onClick}>
          {action.label}
        </button>
      ) : null}
    </main>
  );
}

export function Modal({
  title,
  description,
  onClose,
  children,
}: {
  title: string;
  description: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true">
        <button className="close-button" aria-label="Close" onClick={onClose}>
          ×
        </button>
        <span className="eyebrow">Server mutation</span>
        <h2>{title}</h2>
        <p>{description}</p>
        {children}
      </section>
    </div>
  );
}

export function SubmitActions({
  busy,
  submitLabel,
  onCancel,
}: {
  busy: boolean;
  submitLabel: string;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="modal-actions">
      <button type="button" className="secondary-button" onClick={onCancel}>
        {t("Cancel")}
      </button>
      <button type="submit" className="primary-button" disabled={busy}>
        {busy ? t("Submitting…") : submitLabel}
      </button>
    </div>
  );
}

export type FormHandler = (event: FormEvent<HTMLFormElement>) => void;
