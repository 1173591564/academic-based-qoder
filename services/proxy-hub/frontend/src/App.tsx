import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "./api";
import { CenteredState, navigate } from "./components";
import { LanguageToggle, useI18n } from "./i18n";
import { AuditPage } from "./pages/AuditPage";
import { BackendsPage } from "./pages/BackendsPage";
import { GuidePage } from "./pages/GuidePage";
import { OverviewPage } from "./pages/OverviewPage";
import { PrincipalsPage } from "./pages/PrincipalsPage";
import {
  TenantsPage,
  tenantRouteFromPath,
} from "./pages/TenantsPage";
import { UsagePage } from "./pages/UsagePage";
import type { AdminMe, Overview, Tenant, TenantList } from "./types";

type LoadState =
  | { kind: "loading" }
  | { kind: "unauthenticated" }
  | { kind: "denied"; message: string }
  | { kind: "unavailable"; message: string; requestId: string | null }
  | {
      kind: "ready";
      me: AdminMe;
      overview: Overview;
      tenants: Tenant[];
    };

export interface NavigationItem {
  label: string;
  icon: string;
  path: string;
  capability?: string;
  section?: string;
}

const NAVIGATION: NavigationItem[] = [
  { label: "Overview", icon: "⌂", path: "/console/" },
  { label: "Tenants", icon: "◇", path: "/console/tenants" },
  {
    label: "Backends",
    icon: "↗",
    path: "/console/backends",
    capability: "backend:read",
    section: "Operations",
  },
  {
    label: "Audit",
    icon: "≡",
    path: "/console/audit",
    capability: "audit:read",
  },
  {
    label: "Usage",
    icon: "◫",
    path: "/console/usage",
    capability: "usage:read",
  },
  {
    label: "Principals",
    icon: "○",
    path: "/console/principals",
    capability: "principal:manage",
    section: "Identity",
  },
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

export function isNavigationItemVisible(
  item: NavigationItem,
  capabilities: string[],
): boolean {
  return !item.capability || capabilities.includes(item.capability);
}

function isActive(path: string, itemPath: string): boolean {
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
      const [overview, tenants] = await Promise.all([
        api.get<Overview>("/v1/admin/overview"),
        api.get<TenantList>("/v1/admin/tenants"),
      ]);
      setState({
        kind: "ready",
        me: me.data,
        overview: overview.data,
        tenants: tenants.data.items,
      });
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
    return <CenteredLoading />;
  }
  if (state.kind === "unauthenticated") {
    const returnTo = encodeURIComponent(window.location.pathname);
    return (
      <CenteredAuth
        returnTo={returnTo}
      />
    );
  }
  if (state.kind === "denied") {
    return <CenteredDenied message={state.message} />;
  }
  if (state.kind === "unavailable") {
    return (
      <CenteredUnavailable
        message={state.message}
        requestId={state.requestId}
        onRetry={() => void load()}
      />
    );
  }

  const visibleNavigation = NAVIGATION.filter((item) =>
    isNavigationItemVisible(item, state.me.capabilities),
  );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t("Skip to content")}
      </a>
      <aside
        className={
          mobileNavigationOpen ? "sidebar mobile-open" : "sidebar"
        }
      >
        <div className="brand">
          <div className="brand-mark">S</div>
          <div>
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
          {visibleNavigation.map((item, index) => (
            <div className="nav-entry" key={item.path}>
              {item.section &&
              visibleNavigation
                .slice(0, index)
                .every((previous) => previous.section !== item.section) ? (
                <div className="nav-section">{t(item.section)}</div>
              ) : null}
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
          <div>
            <strong>{principalLabel}</strong>
            <span>
              {state.me.roles[0]?.role.replaceAll("_", " ") ?? "No role"}
            </span>
          </div>
          <LanguageToggle />
        </div>
      </aside>
      <main className="main" id="main-content" tabIndex={-1}>
        <ConsolePage
          path={path}
          me={state.me}
          overview={state.overview}
          tenants={state.tenants}
          onReload={load}
        />
      </main>
    </div>
  );
}

function CenteredLoading() {
  const { t } = useI18n();
  return <CenteredState title={t("Loading control plane")} pulse />;
}

function CenteredAuth({ returnTo }: { returnTo: string }) {
  const { t } = useI18n();
  return (
    <CenteredState
      title={t("Operator access")}
      message={t(
        "Sign in through the configured identity provider to manage Proxy Hub.",
      )}
      action={{
        label: t("Sign in with OIDC"),
        href: `/auth/login?return_to=${returnTo}`,
      }}
    />
  );
}

function CenteredDenied({ message }: { message: string }) {
  const { t } = useI18n();
  return <CenteredState title={t("Access denied")} message={message} />;
}

function CenteredUnavailable({
  message,
  requestId,
  onRetry,
}: {
  message: string;
  requestId: string | null;
  onRetry: () => void;
}) {
  const { t } = useI18n();
  return (
    <CenteredState
      title={t("Control plane unavailable")}
      message={t(message)}
      requestId={requestId}
      action={{ label: t("Retry"), onClick: onRetry }}
    />
  );
}

function ConsolePage({
  path,
  me,
  overview,
  tenants,
  onReload,
}: {
  path: string;
  me: AdminMe;
  overview: Overview;
  tenants: Tenant[];
  onReload: () => Promise<void>;
}) {
  if (path.startsWith("/console/guide")) {
    return <GuidePage />;
  }
  if (path.startsWith("/console/tenants")) {
    return (
      <TenantsPage
        me={me}
        tenants={tenants}
        route={tenantRouteFromPath(path)}
        onReload={onReload}
      />
    );
  }
  if (path.startsWith("/console/backends")) {
    return me.capabilities.includes("backend:read") ? (
      <BackendsPage me={me} />
    ) : (
      <DeniedPage />
    );
  }
  if (path.startsWith("/console/audit")) {
    return me.capabilities.includes("audit:read") ? (
      <AuditPage me={me} tenants={tenants} />
    ) : (
      <DeniedPage />
    );
  }
  if (path.startsWith("/console/usage")) {
    return me.capabilities.includes("usage:read") ? (
      <UsagePage me={me} tenants={tenants} />
    ) : (
      <DeniedPage />
    );
  }
  if (path.startsWith("/console/principals")) {
    return me.capabilities.includes("principal:manage") ? (
      <PrincipalsPage />
    ) : (
      <DeniedPage />
    );
  }
  return <OverviewPage overview={overview} tenants={tenants} />;
}

function DeniedPage() {
  const { t } = useI18n();
  return (
    <section className="panel panel-state">
      <h3>{t("Access denied")}</h3>
      <p>
        {t(
          "This browser session does not advertise the capability for this page.",
        )}
      </p>
      <button className="secondary-button" onClick={() => navigate("/console/")}>
        {t("Return to overview")}
      </button>
    </section>
  );
}
