import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import { useI18n } from "../i18n";
import { navigate } from "../components";
import type { ListResponse, ScholarBackend, Tenant } from "../types";

interface StepState {
  done: boolean;
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
      hint: t("checklist.s1.hint"),
      link: { label: t("Tenants"), path: "/console/tenants" },
    },
    {
      done: probe?.members ?? false,
      hint: t("checklist.s2.hint"),
      link: tenant
        ? {
            label: t("Members"),
            path: `/console/tenants/${encodeURIComponent(tenant.id)}/access`,
          }
        : undefined,
    },
    {
      done: (probe?.tools ?? false) && (probe?.quota ?? false),
      hint: t("checklist.s3.hint"),
      link: tenant
        ? {
            label: t("Policy, quota & route"),
            path: `/console/tenants/${encodeURIComponent(tenant.id)}/policies`,
          }
        : undefined,
    },
    {
      done: (backends?.length ?? 0) > 0,
      hint: t("checklist.s4.hint"),
      link: { label: t("Backends"), path: "/console/backends" },
    },
    {
      done: activeBackend,
      hint: t("checklist.s5.hint"),
      link: { label: t("Backends"), path: "/console/backends" },
    },
    {
      done: probe?.route ?? false,
      hint: t("checklist.s6.hint"),
      link: tenant
        ? {
            label: t("Policy, quota & route"),
            path: `/console/tenants/${encodeURIComponent(tenant.id)}/policies`,
          }
        : undefined,
    },
    {
      done: probe?.enrolment ?? false,
      hint: t("checklist.s7.hint"),
      link: tenant
        ? {
            label: t("Enrolments"),
            path: `/console/tenants/${encodeURIComponent(tenant.id)}/access`,
          }
        : undefined,
    },
    {
      done: false,
      hint: t("checklist.s8.hint"),
    },
  ];

  const doneCount = steps.filter((s) => s.done).length;
  const total = steps.length;
  const allDone = doneCount >= total - 1; // step 8 completes outside the console

  if (dismissed) {
    return null;
  }

  return (
    <section className="panel checklist" aria-label="Setup checklist">
      <div className="checklist-head">
        <div>
          <span className="eyebrow">{t("GETTING STARTED")}</span>
          <h2>{t("Quick start")}</h2>
        </div>
        <div className="checklist-actions">
          <span className="mono">
            {doneCount}/{total}
          </span>
          <button
            className="text-button"
            onClick={() => setCollapsed((c) => !c)}
          >
            {collapsed ? t("Expand") : t("Collapse")}
          </button>
          <button
            className="text-button"
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
      <div className="checklist-bar">
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
                className={step.done ? "checklist-step done" : "checklist-step"}
                key={step.hint}
              >
                <span className="checklist-mark">{step.done ? "✓" : index + 1}</span>
                <div>
                  <strong>{t(`checklist.s${index + 1}.title`)}</strong>
                  <p>{step.hint}</p>
                  {step.link ? (
                    <button
                      className="text-button"
                      onClick={() => navigate(step.link!.path)}
                    >
                      {step.link.label} →
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
          {allDone ? (
            <p className="checklist-footer">{t("checklist.allDone")}</p>
          ) : (
            <p className="checklist-footer">
              <button
                className="text-button"
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
