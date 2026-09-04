import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "./api";
import { CenteredState, navigate } from "./components";
import { LanguageToggle, useI18n } from "./i18n";
import { ServiceStatusPage } from "./pages/ServiceStatusPage";
import { TokenAuditPage } from "./pages/TokenAuditPage";
import { TokensPage } from "./pages/TokensPage";
import type { AdminMe } from "./types";

type LoadState =
  | { kind: "loading" }
  | { kind: "unauthenticated" }
  | { kind: "denied"; message: string }
  | { kind: "unavailable"; message: string; requestId: string | null }
  | { kind: "ready"; me: AdminMe };

export interface NavigationItem {
  label: string;
  icon: string;
  path: string;
}

export const NAVIGATION: NavigationItem[] = [
  { label: "Token management", icon: "◇", path: "/console/" },
  { label: "Service status", icon: "◉", path: "/console/status" },
  { label: "Audit log", icon: "≡", path: "/console/audit" },
];

function errorState(error: unknown): LoadState {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return { kind: "unauthenticated" };
    }
    if (error.status === 403) {
      return { kind: "denied", message: error.message };
    }
    return {
      kind: "unavailable",
      message: error.message,
      requestId: error.requestId,
    };
  }
  return {
    kind: "unavailable",
    message: "The administration API is unavailable.",
    requestId: null,
  };
}

export function isActive(path: string, itemPath: string): boolean {
  if (itemPath === "/console/") {
    return path === "/console" || path === "/console/";
  }
  return path === itemPath || path.startsWith(`${itemPath}/`);
}

export function App() {
  const { t } = useI18n();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [path, setPath] = useState(window.location.pathname);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const me = await api.get<AdminMe>("/v1/admin/me");
      setState({ kind: "ready", me: me.data });
    } catch (error) {
      setState(errorState(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onPopState = () => {
      setPath(window.location.pathname);
      setMobileNavigationOpen(false);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const principalLabel = useMemo(() => {
    if (state.kind !== "ready") {
      return "";
    }
    return (
      state.me.principal.display_name ??
      state.me.principal.email ??
      state.me.principal.id
    );
  }, [state]);

  if (state.kind === "loading") {
    return <CenteredState title={t("Loading Proxy Hub")} pulse />;
  }
  if (state.kind === "unauthenticated") {
    const returnTo = encodeURIComponent(window.location.pathname);
    return (
      <CenteredState
        title={t("Administrator access")}
        message={t("Sign in with OIDC to manage Scholar Tokens.")}
        action={{
          label: t("Sign in with OIDC"),
          href: `/auth/login?return_to=${returnTo}`,
        }}
      />
    );
  }
  if (state.kind === "denied") {
    return <CenteredState title={t("Access denied")} message={state.message} />;
  }
  if (state.kind === "unavailable") {
    return (
      <CenteredState
        title={t("Proxy Hub unavailable")}
        message={state.message}
        requestId={state.requestId}
        action={{ label: t("Retry"), onClick: () => void load() }}
      />
    );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t("Skip to content")}
      </a>
      <aside
        className={mobileNavigationOpen ? "sidebar mobile-open" : "sidebar"}
      >
        <div className="brand">
          <div className="brand-mark">S</div>
          <div className="brand-copy">
            <strong>Scholar</strong>
            <span>Proxy Hub</span>
          </div>
          <button
            className="mobile-menu-button"
            type="button"
            aria-label={
              mobileNavigationOpen ? t("Close menu") : t("Open menu")
            }
            aria-expanded={mobileNavigationOpen}
            aria-controls="primary-navigation"
            onClick={() => setMobileNavigationOpen((open) => !open)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
        <nav id="primary-navigation" aria-label={t("Primary navigation")}>
          {NAVIGATION.map((item) => (
            <div className="nav-entry" key={item.path}>
              <button
                className={isActive(path, item.path) ? "nav-item active" : "nav-item"}
                type="button"
                aria-current={isActive(path, item.path) ? "page" : undefined}
                title={t(item.label)}
                onClick={() => navigate(item.path)}
              >
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="nav-label">{t(item.label)}</span>
              </button>
            </div>
          ))}
        </nav>
        <div className="identity">
          <div className="avatar">{principalLabel.slice(0, 1).toUpperCase()}</div>
          <div className="identity-copy">
            <strong>{principalLabel}</strong>
            <span>{t("Administrator")}</span>
          </div>
          <LanguageToggle />
        </div>
      </aside>
      <main className="main" id="main-content" tabIndex={-1}>
        {path.startsWith("/console/status") ? (
          <ServiceStatusPage />
        ) : path.startsWith("/console/audit") ? (
          <TokenAuditPage />
        ) : (
          <TokensPage />
        )}
      </main>
    </div>
  );
}
