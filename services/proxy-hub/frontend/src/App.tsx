import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "./api";
import { CenteredState, navigate } from "./components";
import { AuditPage } from "./pages/AuditPage";
import { BackendsPage } from "./pages/BackendsPage";
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
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [path, setPath] = useState(window.location.pathname);

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
    const onPopState = () => setPath(window.location.pathname);
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
    return <CenteredState title="Loading control plane" pulse />;
  }
  if (state.kind === "unauthenticated") {
    const returnTo = encodeURIComponent(window.location.pathname);
    return (
      <CenteredState
        title="Operator access"
        message="Sign in through the configured identity provider to manage Proxy Hub."
        action={{
          label: "Sign in with OIDC",
          href: `/auth/login?return_to=${returnTo}`,
        }}
      />
    );
  }
  if (state.kind === "denied") {
    return <CenteredState title="Access denied" message={state.message} />;
  }
  if (state.kind === "unavailable") {
    return (
      <CenteredState
        title="Control plane unavailable"
        message={state.message}
        requestId={state.requestId}
        action={{ label: "Retry", onClick: () => void load() }}
      />
    );
  }

  const visibleNavigation = NAVIGATION.filter((item) =>
    isNavigationItemVisible(item, state.me.capabilities),
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div>
            <strong>Scholar</strong>
            <span>Proxy Hub</span>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          {visibleNavigation.map((item, index) => (
            <div className="nav-entry" key={item.path}>
              {item.section &&
              visibleNavigation
                .slice(0, index)
                .every((previous) => previous.section !== item.section) ? (
                <div className="nav-section">{item.section}</div>
              ) : null}
              <button
                className={isActive(path, item.path) ? "nav-item active" : "nav-item"}
                onClick={() => navigate(item.path)}
              >
                <span className="nav-icon">{item.icon}</span>
                {item.label}
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
        </div>
      </aside>
      <main className="main">
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
  return (
    <section className="panel panel-state">
      <h3>Access denied</h3>
      <p>This browser session does not advertise the capability for this page.</p>
      <button className="secondary-button" onClick={() => navigate("/console/")}>
        Return to overview
      </button>
    </section>
  );
}
