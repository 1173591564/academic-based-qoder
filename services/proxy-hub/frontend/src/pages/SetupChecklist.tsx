import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import { useI18n } from "../i18n";
import { navigate } from "../components";
import type { ListResponse, ScholarBackend, Tenant } from "../types";

interface StepState {
  done: boolean;
  title: string;
  hint: string;
  link?: { label: string; path: string };
}

const DISMISS_KEY = "proxy_hub_checklist_dismissed";

export function SetupChecklist({ tenants }: { tenants: Tenant[] }) {
  const { t } = useI18n();
  const [dismissed, setDismissed] = useState(() => {
    try {
      return window.localStorage.getItem(DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [collapsed, setCollapsed] = useState(false);
  const [backends, setBackends] = useState<ScholarBackend[] | null>(null);
  const [probe, setProbe] = useState<{
    members: boolean;
    tools: boolean;
    quota: boolean;
    route: boolean;
    enrolment: boolean;
  } | null>(null);

  const tenant = useMemo(
    () => tenants.find((x) => x.status === "active") ?? tenants[0] ?? null,
    [tenants],
  );

  useEffect(() => {
    let cancelled = false;
    async function probeTenant() {
      if (!tenant) {
        setProbe({ members: false, tools: false, quota: false, route: false, enrolment: false });
        return;
      }
      const prefix = `/v1/admin/tenants/${encodeURIComponent(tenant.id)}`;
      const flag = async <T,>(path: string, predicate: (data: T) => boolean): Promise<boolean> => {
        try {
          const result = await api.get<T>(path);
          return predicate(result.data);
        } catch {
          return false;
        }
      };
      const [members, tools, quota, route, enrolment] = await Promise.all([
        flag<ListResponse<{ id: string }>>(`${prefix}/memberships`, (d) => d.items.length > 0),
        flag<{ allowed_tools: string[] }>(`${prefix}/tool-policy`, (d) => d.allowed_tools.length > 0),
        flag<{ enforcement_enabled: boolean }>(`${prefix}/quota-policy`, (d) => d.enforcement_enabled),
        flag<{ status: string }>(`${prefix}/backend-route`, (d) => d.status === "active"),
        flag<ListResponse<{ id: string }>>(`${prefix}/enrolments`, (d) => d.items.length > 0),
      ]);
      if (!cancelled) {
        setProbe({ members, tools, quota, route, enrolment });
      }
    }
    void probeTenant();
    return () => {
      cancelled = true;
    };
  }, [tenant]);

  useEffect(() => {
    let cancelled = false;
    async function loadBackends() {
      try {
        const result = await api.get<ListResponse<ScholarBackend>>("/v1/admin/backends");
        if (!cancelled) {
          setBackends(result.data.items);
        }
      } catch {
        if (!cancelled) {
          setBackends([]);
        }
      }
    }
    void loadBackends();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeBackend = useMemo(
    () =>
      (backends ?? []).some((b) => b.status === "active" && b.probe.ready === true),
    [backends],
  );

  const steps: StepState[] = [
    {
      done: tenants.length > 0,
      title: t("Create a tenant"),
      hint: t(
        "Establish the organization boundary; tools, quotas, and routes belong to a tenant.",
      ),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      done: probe?.members ?? false,
      title: t("Add members"),
      hint: t(
        "After a teammate signs in with OIDC, add their principal to the tenant.",
      ),
      link: tenant
        ? {
            label: t("Members"),
            path: `/console/tenants/${encodeURIComponent(tenant.id)}/access`,
          }
        : undefined,
    },
    {
      done: (probe?.tools ?? false) && (probe?.quota ?? false),
      title: t("Configure policy and quota"),
      hint: t(
        "Start from deny-all, allow the required tools, and set request and concurrency limits.",
      ),
      link: tenant
        ? {
            label: t("Policy, quota & route"),
            path: `/console/tenants/${encodeURIComponent(tenant.id)}/policies`,
          }
        : undefined,
    },
    {
      done: (backends?.length ?? 0) > 0,
      title: t("Register a backend"),
      hint: t("Register the Scholar data plane URL and corpus version."),
      link: { label: t("Backends"), path: "/console/backends" },
    },
    {
      done: activeBackend,
      title: t("Probe and activate"),
      hint: t(
        "Verify readiness and the corpus version before activating the backend.",
      ),
      link: { label: t("Backends"), path: "/console/backends" },
    },
    {
      done: probe?.route ?? false,
      title: t("Bind the tenant route"),
      hint: t("Route the tenant's MCP calls to the active backend."),
      link: tenant
        ? {
            label: t("Policy, quota & route"),
            path: `/console/tenants/${encodeURIComponent(tenant.id)}/policies`,
          }
        : undefined,
    },
    {
      done: probe?.enrolment ?? false,
      title: t("Issue an enrolment code"),
      hint: t(
        "Issue a one-time access code and send it privately to the teammate.",
      ),
      link: tenant
        ? {
            label: t("Enrolments"),
            path: `/console/tenants/${encodeURIComponent(tenant.id)}/access`,
          }
        : undefined,
    },
    {
      done: false,
      title: t("Connect a teammate"),
      hint: t(
        "After installing the bundle, run scholar gateway-login --code <enrolment-code>.",
      ),
    },
  ];

  const trackedSteps = steps.slice(0, -1);
  const doneCount = trackedSteps.filter((step) => step.done).length;
  const total = trackedSteps.length;
  const checking = backends === null || probe === null;
  const nextStep = steps.findIndex((step) => !step.done);
  const allDone = doneCount === total;

  if (dismissed) {
    return null;
  }

  return (
    <section
      className="panel checklist"
      aria-labelledby="setup-checklist-title"
      aria-busy={checking}
    >
      <div className="checklist-head">
        <div>
          <span className="eyebrow">{t("GETTING STARTED")}</span>
          <h2 id="setup-checklist-title">{t("Quick start")}</h2>
        </div>
        <div className="checklist-actions">
          <span className="mono">
            {checking
              ? t("Checking setup…")
              : `${doneCount}/${total} ${t("checks")}`}
          </span>
          <button
            className="text-button"
            type="button"
            aria-expanded={!collapsed}
            onClick={() => setCollapsed((c) => !c)}
          >
            {collapsed ? t("Expand") : t("Collapse")}
          </button>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setDismissed(true);
              try {
                window.localStorage.setItem(DISMISS_KEY, "1");
              } catch {
                // storage unavailable
              }
            }}
          >
            {t("Hide")}
          </button>
        </div>
      </div>
      <div
        className="checklist-bar"
        role="progressbar"
        aria-label={t("Setup progress")}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={doneCount}
      >
        <div
          className="checklist-bar-fill"
          style={{ width: `${Math.round((doneCount / total) * 100)}%` }}
        />
      </div>
      {collapsed ? null : (
        <>
          <ol className="checklist-grid">
            {steps.map((step, index) => (
              <li
                className={[
                  "checklist-step",
                  step.done ? "done" : "",
                  !checking && index === nextStep ? "current" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                key={index}
              >
                <span className="checklist-mark" aria-hidden="true">
                  {step.done ? "✓" : index + 1}
                </span>
                <div>
                  <div className="checklist-title">
                    <strong>{step.title}</strong>
                    {!checking && index === nextStep ? (
                      <span>{t("Next step")}</span>
                    ) : null}
                  </div>
                  <p>{step.hint}</p>
                  {step.link ? (
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => {
                        if (step.link) {
                          navigate(step.link.path);
                        }
                      }}
                    >
                      {step.link.label} <span aria-hidden="true">→</span>
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
          {allDone ? (
            <p className="checklist-footer">
              {t(
                "Setup complete. Teammates can now use the academic platform through the gateway.",
              )}
            </p>
          ) : (
            <p className="checklist-footer">
              <button
                className="text-button"
                type="button"
                onClick={() => navigate("/console/guide")}
              >
                {t("View the detailed guide")}
              </button>
            </p>
          )}
        </>
      )}
    </section>
  );
}
