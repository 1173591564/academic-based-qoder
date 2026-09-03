import {
  useEffect,
  useId,
  useRef,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { statusLabel, useI18n } from "./i18n";

export function navigate(path: string): void {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function activateOnKeyDown(
  event: KeyboardEvent<HTMLElement>,
  action: () => void,
): void {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
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
        <button className="primary-button" type="button" onClick={action.onClick}>
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
      <div className={`metric-dot ${tone}`} aria-hidden="true" />
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

export function StatusPill({ status }: { status: string }) {
  const { t } = useI18n();
  const tone =
    status === "active" || status === "ready" || status === "forwarded"
      ? "active"
      : status === "pending" || status === "probing"
        ? "pending"
        : status === "disabled" ||
            status === "denied" ||
            status === "failed" ||
            status === "rejected" ||
            status === "revoked"
          ? "disabled"
          : "neutral";
  return (
    <span className={`status ${tone}`}>
      <i aria-hidden="true" />
      {statusLabel(status, t)}
    </span>
  );
}

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">
        ◇
      </div>
      <h3>{title}</h3>
      <p>{message}</p>
      {action ? (
        <button className="secondary-button" type="button" onClick={action.onClick}>
          {action.label}
        </button>
      ) : null}
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
    <div className="inline-alert" role="alert" aria-live="assertive">
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
  const { t } = useI18n();
  return (
    <div className="server-notice" role="status" aria-live="polite">
      <span>{message}</span>
      <button
        type="button"
        aria-label={t("Dismiss server response")}
        onClick={onClose}
      >
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
    return (
      <div
        className="panel-state loading-state"
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <span>{t("Loading server data…")}</span>
        <div className="loading-skeleton" aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
      </div>
    );
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
    <main
      className="centered-state"
      role={pulse ? "status" : undefined}
      aria-live={pulse ? "polite" : undefined}
      aria-busy={pulse || undefined}
    >
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
  const { t } = useI18n();
  const titleId = useId();
  const descriptionId = useId();
  const modalRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const frame = window.requestAnimationFrame(() => {
      if (!modalRef.current?.contains(document.activeElement)) {
        const field = modalRef.current?.querySelector<HTMLElement>(
          "input:not(:disabled), select:not(:disabled)",
        );
        (field ?? modalRef.current)?.focus();
      }
    });
    return () => {
      window.cancelAnimationFrame(frame);
      previousFocus?.focus();
    };
  }, []);

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !modalRef.current) {
      return;
    }
    const focusable = Array.from(
      modalRef.current.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input:not(:disabled), select:not(:disabled), [href], [tabindex]:not([tabindex="-1"])',
      ),
    );
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first || !last) {
      return;
    }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      className="modal-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        className="modal"
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
      >
        <button
          className="close-button"
          type="button"
          aria-label={t("Close")}
          onClick={onClose}
        >
          ×
        </button>
        <span className="eyebrow">{t("Server mutation")}</span>
        <h2 id={titleId}>{title}</h2>
        <p id={descriptionId}>{description}</p>
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
      <button
        type="button"
        className="secondary-button"
        onClick={onCancel}
      >
        {t("Cancel")}
      </button>
      <button
        type="submit"
        className="primary-button"
        disabled={busy}
        aria-busy={busy}
      >
        {busy ? t("Submitting…") : submitLabel}
      </button>
    </div>
  );
}

export type FormHandler = (event: FormEvent<HTMLFormElement>) => void;
