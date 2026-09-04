import { useCallback, useEffect, useState } from "react";

import { api, ApiError, idempotencyKey } from "../api";
import {
  EmptyState,
  InlineAlert,
  Modal,
  PanelState,
  ServerNotice,
  StatusPill,
  SubmitActions,
} from "../components";
import { useI18n } from "../i18n";
import { loadFailure, type LoadFailure } from "../load";
import type {
  ListResponse,
  ManagedResearcher,
  Membership,
  ResearcherCreateResponse,
  RoleBinding,
  ScholarAccessKey,
  Team,
  ToolPolicy,
} from "../types";

interface AccessData {
  teams: Team[];
  researchers: ManagedResearcher[];
  accessKeys: ScholarAccessKey[];
  memberships: Membership[];
  roles: RoleBinding[];
  allowedTools: string[];
}

type AccessLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: AccessData }
  | LoadFailure;

function ToolSelector({
  tools,
  selected,
  t,
}: {
  tools: string[];
  selected?: string[];
  t: (key: string) => string;
}) {
  return (
    <fieldset className="tool-selector">
      <legend>{t("Allowed Scholar tools")}</legend>
      <p>{t("Access Keys can only use tools allowed by tenant policy.")}</p>
      {tools.length === 0 ? (
        <InlineAlert message={t("Configure the tenant tool policy first.")} />
      ) : (
        <div className="tool-option-grid">
          {tools.map((tool) => (
            <label key={tool}>
              <input
                type="checkbox"
                name="allowed_tools"
                value={tool}
                defaultChecked={selected?.includes(tool) ?? true}
              />
              <span>{tool}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

async function loadAllowedTools(path: string): Promise<string[]> {
  try {
    return (await api.get<ToolPolicy>(path)).data.allowed_tools;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return [];
    }
    throw error;
  }
}

export function TenantAccess({ tenantId }: { tenantId: string }) {
  const [state, setState] = useState<AccessLoad>({ kind: "loading" });
  const [modal, setModal] = useState<
    | "researcher"
    | "key"
    | "editKey"
    | "rotate"
    | "team"
    | "membership"
    | "role"
    | null
  >(null);
  const [selectedResearcher, setSelectedResearcher] =
    useState<ManagedResearcher | null>(null);
  const [selectedKey, setSelectedKey] = useState<ScholarAccessKey | null>(null);
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorRequestId, setErrorRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { t } = useI18n();

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const prefix = `/v1/admin/tenants/${encodeURIComponent(tenantId)}`;
      const [teams, researchers, accessKeys, memberships, roles, toolPolicy] =
        await Promise.all([
        api.get<ListResponse<Team>>(`${prefix}/teams`),
        api.get<ListResponse<ManagedResearcher>>(`${prefix}/researchers`),
        api.get<ListResponse<ScholarAccessKey>>(`${prefix}/access-keys`),
        api.get<ListResponse<Membership>>(`${prefix}/memberships`),
        api.get<ListResponse<RoleBinding>>(`${prefix}/role-bindings`),
        loadAllowedTools(`${prefix}/tool-policy`),
      ]);
      setState({
        kind: "ready",
        data: {
          teams: teams.data.items,
          researchers: researchers.data.items,
          accessKeys: accessKeys.data.items,
          memberships: memberships.data.items,
          roles: roles.data.items,
          allowedTools: toolPolicy,
        },
      });
    } catch (loadError) {
      setState(loadFailure(loadError));
    }
  }, [tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  function mutationFailed(mutationError: unknown, fallback: string) {
    setError(
      mutationError instanceof ApiError ? mutationError.message : fallback,
    );
    setErrorRequestId(
      mutationError instanceof ApiError ? mutationError.requestId : null,
    );
    if (mutationError instanceof ApiError && mutationError.status === 412) {
      void load();
    }
  }

  function clearMutationError(): void {
    setError(null);
    setErrorRequestId(null);
  }

  function keySettings(form: FormData) {
    const requestLimit = String(form.get("request_limit") ?? "").trim();
    const periodSeconds = String(form.get("period_seconds") ?? "").trim();
    return {
      label: String(form.get("label") ?? "").trim(),
      allowed_tools: form.getAll("allowed_tools").map(String),
      expires_in_seconds:
        Number(String(form.get("expires_in_days") ?? "30")) * 86400,
      request_limit: requestLimit ? Number(requestLimit) : null,
      period_seconds: periodSeconds ? Number(periodSeconds) : null,
    };
  }

  async function createResearcher(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("researcher");
    clearMutationError();
    try {
      const result = await api.post<ResearcherCreateResponse>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/researchers`,
        {
          display_name: String(form.get("display_name") ?? "").trim(),
          email: String(form.get("email") ?? "").trim() || null,
          team_id: String(form.get("team_id") ?? "").trim() || null,
          ...keySettings(form),
        },
        { "Idempotency-Key": idempotencyKey() },
      );
      setIssuedKey(result.data.access_key.access_key);
      setModal(null);
      setNotice(t("Researcher and Access Key created."));
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Researcher creation failed."));
    } finally {
      setBusy(null);
    }
  }

  async function createAccessKey(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedResearcher === null) {
      return;
    }
    const form = new FormData(event.currentTarget);
    setBusy("key");
    clearMutationError();
    try {
      const result = await api.post<ScholarAccessKey>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/researchers/${encodeURIComponent(selectedResearcher.id)}/access-keys`,
        keySettings(form),
        { "Idempotency-Key": idempotencyKey() },
      );
      setIssuedKey(result.data.access_key);
      setModal(null);
      setNotice(t("Access Key created."));
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Access Key creation failed."));
    } finally {
      setBusy(null);
    }
  }

  async function updateAccessKey(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedKey === null) {
      return;
    }
    const form = new FormData(event.currentTarget);
    const requestLimit = String(form.get("request_limit") ?? "").trim();
    const periodSeconds = String(form.get("period_seconds") ?? "").trim();
    setBusy(selectedKey.id);
    clearMutationError();
    try {
      await api.patch<ScholarAccessKey>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/access-keys/${encodeURIComponent(selectedKey.id)}`,
        {
          label: String(form.get("label") ?? "").trim(),
          allowed_tools: form.getAll("allowed_tools").map(String),
          expires_at: new Date(
            String(form.get("expires_at") ?? ""),
          ).toISOString(),
          request_limit: requestLimit ? Number(requestLimit) : null,
          period_seconds: periodSeconds ? Number(periodSeconds) : null,
        },
        selectedKey.etag,
      );
      setModal(null);
      setNotice(t("Access Key updated."));
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Access Key update failed."));
    } finally {
      setBusy(null);
    }
  }

  async function rotateAccessKey(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedKey === null) {
      return;
    }
    const form = new FormData(event.currentTarget);
    setBusy(selectedKey.id);
    clearMutationError();
    try {
      const result = await api.post<ScholarAccessKey>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/access-keys/${encodeURIComponent(selectedKey.id)}/rotate`,
        {
          label: String(form.get("label") ?? "").trim() || null,
          expires_in_seconds:
            Number(String(form.get("expires_in_days") ?? "30")) * 86400,
        },
        {
          "Idempotency-Key": idempotencyKey(),
          "If-Match": selectedKey.etag,
        },
      );
      setIssuedKey(result.data.access_key);
      setModal(null);
      setNotice(t("Access Key rotated."));
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Access Key rotation failed."));
    } finally {
      setBusy(null);
    }
  }

  async function toggleResearcher(researcher: ManagedResearcher) {
    const status = researcher.status === "active" ? "disabled" : "active";
    if (!window.confirm(t("Change this research user's access?"))) {
      return;
    }
    setBusy(researcher.id);
    clearMutationError();
    try {
      await api.patch<ManagedResearcher>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/researchers/${encodeURIComponent(researcher.id)}`,
        { status },
        researcher.etag,
      );
      setNotice(
        status === "active"
          ? t("Research user enabled.")
          : t("Research user disabled."),
      );
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Research user update failed."));
    } finally {
      setBusy(null);
    }
  }

  async function revokeAccessKey(accessKey: ScholarAccessKey) {
    if (!window.confirm(t("Revoke this Access Key immediately?"))) {
      return;
    }
    setBusy(accessKey.id);
    clearMutationError();
    try {
      await api.delete(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/access-keys/${encodeURIComponent(accessKey.id)}`,
        accessKey.etag,
      );
      setNotice(t("Access Key revoked."));
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Access Key revocation failed."));
    } finally {
      setBusy(null);
    }
  }

  async function createTeam(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("team");
    clearMutationError();
    try {
      const result = await api.post<Team>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/teams`,
        { name: String(form.get("name") ?? "").trim() },
        { "Idempotency-Key": idempotencyKey() },
      );
      setModal(null);
      setNotice(
        `Server created team ${result.data.name}, v${result.data.version}, ${result.data.status}.`,
      );
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, "Team creation failed.");
    } finally {
      setBusy(null);
    }
  }

  async function createMembership(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("membership");
    clearMutationError();
    try {
      const result = await api.post<Membership>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/memberships`,
        {
          principal_id: String(form.get("principal_id") ?? "").trim(),
          team_id: String(form.get("team_id") ?? "").trim() || null,
        },
        { "Idempotency-Key": idempotencyKey() },
      );
      setModal(null);
      setNotice(
        `Server created membership ${result.data.id}, v${result.data.version}, ${result.data.status}.`,
      );
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, "Membership creation failed.");
    } finally {
      setBusy(null);
    }
  }

  async function createRole(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("role");
    clearMutationError();
    try {
      const result = await api.post<RoleBinding>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/role-bindings`,
        {
          principal_id: String(form.get("principal_id") ?? "").trim(),
          role: String(form.get("role") ?? ""),
        },
        { "Idempotency-Key": idempotencyKey() },
      );
      setModal(null);
      setNotice(
        `Server created ${result.data.role} role binding ${result.data.id}, v${result.data.version}.`,
      );
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, "Role binding creation failed.");
    } finally {
      setBusy(null);
    }
  }

  async function toggleTeam(team: Team) {
    const status = team.status === "active" ? "disabled" : "active";
    if (!window.confirm(`${status === "active" ? "Enable" : "Disable"} this team?`)) {
      return;
    }
    setBusy(team.id);
    clearMutationError();
    try {
      const result = await api.patch<Team>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/teams/${encodeURIComponent(team.id)}`,
        { status },
        team.etag,
      );
      setNotice(
        `Server returned team ${result.data.name}, v${result.data.version}, ${result.data.status}.`,
      );
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, "Team update failed.");
    } finally {
      setBusy(null);
    }
  }

  async function toggleMembership(membership: Membership) {
    const status = membership.status === "active" ? "disabled" : "active";
    if (
      !window.confirm(
        `${status === "active" ? "Enable" : "Disable"} this membership?`,
      )
    ) {
      return;
    }
    setBusy(membership.id);
    clearMutationError();
    try {
      const result = await api.patch<Membership>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/memberships/${encodeURIComponent(membership.id)}`,
        { status },
        membership.etag,
      );
      setNotice(
        `Server returned membership ${result.data.id}, v${result.data.version}, ${result.data.status}.`,
      );
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, "Membership update failed.");
    } finally {
      setBusy(null);
    }
  }

  async function removeMembership(membership: Membership) {
    if (!window.confirm("Remove this membership from the tenant?")) {
      return;
    }
    setBusy(membership.id);
    clearMutationError();
    try {
      await api.delete(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/memberships/${encodeURIComponent(membership.id)}`,
        membership.etag,
      );
      setNotice(
        `Server accepted membership removal for ${membership.id} (204).`,
      );
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, "Membership removal failed.");
    } finally {
      setBusy(null);
    }
  }

  async function revokeRole(binding: RoleBinding) {
    if (!window.confirm(`Revoke the ${binding.role} role binding?`)) {
      return;
    }
    setBusy(binding.id);
    clearMutationError();
    try {
      await api.delete(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/role-bindings/${encodeURIComponent(binding.id)}`,
        binding.etag,
      );
      setNotice(`Server accepted role binding revocation for ${binding.id} (204).`);
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, "Role binding revocation failed.");
    } finally {
      setBusy(null);
    }
  }

  if (state.kind === "loading") {
    return (
      <section className="panel">
        <PanelState kind="loading" />
      </section>
    );
  }
  if (state.kind === "denied" || state.kind === "unavailable") {
    return (
      <section className="panel">
        <PanelState
          kind={state.kind}
          message={state.message}
          requestId={state.requestId}
          onRetry={() => void load()}
        />
      </section>
    );
  }

  return (
    <>
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {error ? (
        <InlineAlert message={error} requestId={errorRequestId} />
      ) : null}
      {issuedKey ? (
        <section className="issued-key" aria-labelledby="issued-key-title">
          <div>
            <span className="eyebrow">{t("Shown once")}</span>
            <h2 id="issued-key-title">{t("Save this Access Key now")}</h2>
            <p>
              {t(
                "Proxy Hub stores only a digest. This full key cannot be shown again.",
              )}
            </p>
          </div>
          <code>{issuedKey}</code>
          <div className="issued-key-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => void navigator.clipboard.writeText(issuedKey)}
            >
              {t("Copy Access Key")}
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => setIssuedKey(null)}
            >
              {t("I saved it")}
            </button>
          </div>
          <p className="key-command">
            <code>scholar gateway-login --api-key-stdin</code>
          </p>
        </section>
      ) : null}
      <section className="panel researcher-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">{t("Scholar access")}</span>
            <h2>{t("Research users")}</h2>
            <p>
              {t(
                "Create users and issue revocable Access Keys without Dex or enrolment codes.",
              )}
            </p>
          </div>
          <div className="panel-actions">
            <span className="section-count">
              {state.data.researchers.length}
            </span>
            <button
              type="button"
              className="primary-button"
              onClick={() => setModal("researcher")}
            >
              {t("Create research user")}
            </button>
          </div>
        </div>
        {state.data.researchers.length === 0 ? (
          <EmptyState
            title={t("No research users")}
            message={t("Create a user and their first Access Key in one step.")}
            action={{
              label: t("Create research user"),
              onClick: () => setModal("researcher"),
            }}
          />
        ) : (
          <div className="researcher-list">
            {state.data.researchers.map((researcher) => {
              const keys = state.data.accessKeys.filter(
                (accessKey) => accessKey.principal_id === researcher.id,
              );
              return (
                <article className="researcher-card" key={researcher.id}>
                  <header>
                    <div className="record-copy">
                      <strong>{researcher.display_name}</strong>
                      <span>{researcher.email ?? t("No email")}</span>
                    </div>
                    <StatusPill status={researcher.status} />
                    <div className="inline-actions">
                      <button
                        type="button"
                        className="text-button"
                        disabled={
                          busy === researcher.id ||
                          researcher.status !== "active"
                        }
                        onClick={() => {
                          setSelectedResearcher(researcher);
                          setModal("key");
                        }}
                      >
                        {t("New Access Key")}
                      </button>
                      <button
                        type="button"
                        className={
                          researcher.status === "active"
                            ? "text-button danger-text"
                            : "text-button"
                        }
                        disabled={busy === researcher.id}
                        onClick={() => void toggleResearcher(researcher)}
                      >
                        {researcher.status === "active"
                          ? t("Disable")
                          : t("Enable")}
                      </button>
                    </div>
                  </header>
                  {keys.length === 0 ? (
                    <p className="researcher-empty">
                      {t("No Access Keys for this user.")}
                    </p>
                  ) : (
                    <div className="access-key-list">
                      {keys.map((accessKey) => (
                        <div className="access-key-row" key={accessKey.id}>
                          <div className="record-copy">
                            <strong>{accessKey.label}</strong>
                            <span className="mono">
                              {accessKey.token_prefix}••••
                              {accessKey.token_last_four}
                            </span>
                          </div>
                          <StatusPill status={accessKey.status} />
                          <div className="key-metadata">
                            <span>
                              {t("Expires")}{" "}
                              {new Date(accessKey.expires_at).toLocaleDateString()}
                            </span>
                            <span>
                              {accessKey.request_limit === null
                                ? t("No key quota")
                                : `${accessKey.request_limit} / ${accessKey.period_seconds}s`}
                            </span>
                            <span>
                              {accessKey.last_used_at
                                ? `${t("Last used")} ${new Date(
                                    accessKey.last_used_at,
                                  ).toLocaleString()}`
                                : t("Never used")}
                            </span>
                          </div>
                          <div className="tool-chips">
                            {accessKey.allowed_tools.map((tool) => (
                              <span key={tool}>{tool}</span>
                            ))}
                          </div>
                          <div className="inline-actions">
                            <button
                              type="button"
                              className="text-button"
                              disabled={accessKey.status !== "active"}
                              onClick={() => {
                                setSelectedKey(accessKey);
                                setModal("editKey");
                              }}
                            >
                              {t("Edit")}
                            </button>
                            <button
                              type="button"
                              className="text-button"
                              disabled={accessKey.status !== "active"}
                              onClick={() => {
                                setSelectedKey(accessKey);
                                setModal("rotate");
                              }}
                            >
                              {t("Rotate")}
                            </button>
                            <button
                              type="button"
                              className="text-button danger-text"
                              disabled={
                                busy === accessKey.id ||
                                accessKey.status !== "active"
                              }
                              onClick={() => void revokeAccessKey(accessKey)}
                            >
                              {t("Revoke")}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
      <div className="access-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">{t("Organization")}</span>
              <h2>{t("Teams")}</h2>
            </div>
            <div className="panel-actions">
              <span className="section-count">{state.data.teams.length}</span>
              <button
                type="button"
                className="text-button"
                onClick={() => setModal("team")}
              >
                {t("New team")}
              </button>
            </div>
          </div>
          {state.data.teams.length === 0 ? (
            <EmptyState title={t("No teams")} message={t("Create an optional team boundary.")} />
          ) : (
            <div className="record-list">
              {state.data.teams.map((team) => (
                <article key={team.id}>
                  <div className="record-copy">
                    <strong>{team.name}</strong>
                    <span className="mono" title={team.id}>
                      {team.id}
                    </span>
                  </div>
                  <StatusPill status={team.status} />
                  <button
                    type="button"
                    className="text-button"
                    disabled={busy === team.id}
                    aria-busy={busy === team.id}
                    onClick={() => void toggleTeam(team)}
                  >
                    {team.status === "active" ? t("Disable") : t("Enable")}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">{t("Tenant access")}</span>
              <h2>{t("Memberships")}</h2>
            </div>
            <div className="panel-actions">
              <span className="section-count">{state.data.memberships.length}</span>
              <button
                type="button"
                className="text-button"
                onClick={() => setModal("membership")}
              >
                {t("Add member")}
              </button>
            </div>
          </div>
          {state.data.memberships.length === 0 ? (
            <EmptyState
              title={t("No memberships")}
              message={t("Add an active principal to this tenant.")}
            />
          ) : (
            <div className="record-list">
              {state.data.memberships.map((membership) => (
                <article key={membership.id}>
                  <div className="record-copy">
                    <strong title={membership.principal_id}>
                      {membership.principal_id}
                    </strong>
                    <span
                      className={membership.team_id ? "mono" : undefined}
                      title={membership.team_id ?? undefined}
                    >
                      {membership.team_id ?? t("Tenant-wide")}
                    </span>
                  </div>
                  <StatusPill status={membership.status} />
                  <div className="inline-actions">
                    <button
                      type="button"
                      className="text-button"
                      disabled={busy === membership.id}
                      aria-busy={busy === membership.id}
                      onClick={() => void toggleMembership(membership)}
                    >
                      {membership.status === "active" ? t("Disable") : t("Enable")}
                    </button>
                    <button
                      type="button"
                      className="text-button danger-text"
                      disabled={busy === membership.id}
                      aria-busy={busy === membership.id}
                      onClick={() => void removeMembership(membership)}
                    >
                      {t("Remove")}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">{t("Authorization")}</span>
              <h2>{t("Role bindings")}</h2>
            </div>
            <div className="panel-actions">
              <span className="section-count">{state.data.roles.length}</span>
              <button
                type="button"
                className="text-button"
                onClick={() => setModal("role")}
              >
                {t("Bind role")}
              </button>
            </div>
          </div>
          {state.data.roles.length === 0 ? (
            <EmptyState
              title={t("No active bindings")}
              message={t("Bind a tenant role to an active member.")}
            />
          ) : (
            <div className="record-list">
              {state.data.roles.map((binding) => (
                <article key={binding.id}>
                  <div className="record-copy">
                    <strong title={binding.principal_id}>
                      {binding.principal_id}
                    </strong>
                    <span>{binding.role.replaceAll("_", " ")}</span>
                  </div>
                  <span className="mono">v{binding.version}</span>
                  <button
                    type="button"
                    className="text-button danger-text"
                    disabled={busy === binding.id}
                    aria-busy={busy === binding.id}
                    onClick={() => void revokeRole(binding)}
                  >
                    {t("Revoke")}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
      {modal === "researcher" ? (
        <Modal
          title={t("Create research user")}
          description={t(
            "Create the user, tenant membership, and first Access Key together.",
          )}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void createResearcher(event)}>
            <div className="form-grid">
              <label>
                {t("Display name")}
                <input
                  name="display_name"
                  required
                  maxLength={256}
                  autoFocus
                />
              </label>
              <label>
                {t("Email (optional)")}
                <input name="email" type="email" maxLength={320} />
              </label>
              <label>
                {t("Team")}
                <select name="team_id" defaultValue="">
                  <option value="">{t("Tenant-wide")}</option>
                  {state.data.teams
                    .filter((team) => team.status === "active")
                    .map((team) => (
                      <option key={team.id} value={team.id}>
                        {team.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                {t("Access Key label")}
                <input
                  name="label"
                  required
                  maxLength={200}
                  defaultValue={t("Primary device")}
                />
              </label>
              <label>
                {t("Expires in days")}
                <input
                  name="expires_in_days"
                  type="number"
                  min={1}
                  max={3650}
                  defaultValue={30}
                  required
                />
              </label>
              <label>
                {t("Request limit (optional)")}
                <input name="request_limit" type="number" min={1} />
              </label>
              <label>
                {t("Period seconds")}
                <input name="period_seconds" type="number" min={1} />
              </label>
            </div>
            <ToolSelector tools={state.data.allowedTools} t={t} />
            <SubmitActions
              busy={busy === "researcher"}
              submitLabel={t("Create user and Access Key")}
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
      {modal === "key" && selectedResearcher ? (
        <Modal
          title={t("Create Access Key")}
          description={`${selectedResearcher.display_name} · ${t(
            "The full key is shown once.",
          )}`}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void createAccessKey(event)}>
            <div className="form-grid">
              <label>
                {t("Access Key label")}
                <input name="label" required maxLength={200} autoFocus />
              </label>
              <label>
                {t("Expires in days")}
                <input
                  name="expires_in_days"
                  type="number"
                  min={1}
                  max={3650}
                  defaultValue={30}
                  required
                />
              </label>
              <label>
                {t("Request limit (optional)")}
                <input name="request_limit" type="number" min={1} />
              </label>
              <label>
                {t("Period seconds")}
                <input name="period_seconds" type="number" min={1} />
              </label>
            </div>
            <ToolSelector tools={state.data.allowedTools} t={t} />
            <SubmitActions
              busy={busy === "key"}
              submitLabel={t("Create Access Key")}
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
      {modal === "editKey" && selectedKey ? (
        <Modal
          title={t("Edit Access Key")}
          description={t(
            "Changes take effect on the next request and cannot exceed tenant policy.",
          )}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void updateAccessKey(event)}>
            <div className="form-grid">
              <label>
                {t("Access Key label")}
                <input
                  name="label"
                  required
                  maxLength={200}
                  defaultValue={selectedKey.label}
                  autoFocus
                />
              </label>
              <label>
                {t("Expires at")}
                <input
                  name="expires_at"
                  type="datetime-local"
                  defaultValue={selectedKey.expires_at.slice(0, 16)}
                  required
                />
              </label>
              <label>
                {t("Request limit (optional)")}
                <input
                  name="request_limit"
                  type="number"
                  min={1}
                  defaultValue={selectedKey.request_limit ?? ""}
                />
              </label>
              <label>
                {t("Period seconds")}
                <input
                  name="period_seconds"
                  type="number"
                  min={1}
                  defaultValue={selectedKey.period_seconds ?? ""}
                />
              </label>
            </div>
            <ToolSelector
              tools={state.data.allowedTools}
              selected={selectedKey.allowed_tools}
              t={t}
            />
            <SubmitActions
              busy={busy === selectedKey.id}
              submitLabel={t("Save Access Key")}
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
      {modal === "rotate" && selectedKey ? (
        <Modal
          title={t("Rotate Access Key")}
          description={t(
            "The current key is revoked immediately when the replacement is created.",
          )}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void rotateAccessKey(event)}>
            <label>
              {t("New label (optional)")}
              <input
                name="label"
                maxLength={200}
                defaultValue={selectedKey.label}
                autoFocus
              />
            </label>
            <label>
              {t("Expires in days")}
              <input
                name="expires_in_days"
                type="number"
                min={1}
                max={3650}
                defaultValue={30}
                required
              />
            </label>
            <SubmitActions
              busy={busy === selectedKey.id}
              submitLabel={t("Rotate Access Key")}
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
      {modal === "team" ? (
        <Modal
          title={t("Create team")}
          description={t("Teams create an optional grouping boundary inside this tenant.")}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void createTeam(event)}>
            <label>
              {t("Team name")}
              <input name="name" required maxLength={200} autoFocus />
            </label>
            <SubmitActions
              busy={busy === "team"}
              submitLabel={t("Create team")}
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
      {modal === "membership" ? (
        <Modal
          title={t("Add membership")}
          description={t("The principal must already be active. Team assignment is optional.")}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void createMembership(event)}>
            <label>
              {t("Principal ID")}
              <input name="principal_id" required maxLength={48} autoFocus />
            </label>
            <label>
              {t("Team")}
              <select name="team_id" defaultValue="">
                <option value="">{t("Tenant-wide")}</option>
                {state.data.teams
                  .filter((team) => team.status === "active")
                  .map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name}
                    </option>
                  ))}
              </select>
            </label>
            <SubmitActions
              busy={busy === "membership"}
              submitLabel={t("Add membership")}
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
      {modal === "role" ? (
        <Modal
          title={t("Bind tenant role")}
          description={t("The principal must have an active membership in this tenant.")}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void createRole(event)}>
            <label>
              {t("Principal ID")}
              <input name="principal_id" required maxLength={48} autoFocus />
            </label>
            <label>
              {t("Role")}
              <select name="role" defaultValue="operator">
                <option value="tenant_admin">{t("Tenant admin")}</option>
                <option value="operator">{t("Operator")}</option>
                <option value="auditor">{t("Auditor")}</option>
              </select>
            </label>
            <SubmitActions
              busy={busy === "role"}
              submitLabel={t("Bind role")}
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
    </>
  );
}
