import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";
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
  Membership,
  RoleBinding,
  Team,
} from "../types";

interface AccessData {
  teams: Team[];
  memberships: Membership[];
  roles: RoleBinding[];
}

type AccessLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: AccessData }
  | LoadFailure;

export function TenantAccess({ tenantId }: { tenantId: string }) {
  const [state, setState] = useState<AccessLoad>({ kind: "loading" });
  const [modal, setModal] = useState<"team" | "membership" | "role" | null>(
    null,
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { t } = useI18n();

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const prefix = `/v1/admin/tenants/${encodeURIComponent(tenantId)}`;
      const [teams, memberships, roles] = await Promise.all([
        api.get<ListResponse<Team>>(`${prefix}/teams`),
        api.get<ListResponse<Membership>>(`${prefix}/memberships`),
        api.get<ListResponse<RoleBinding>>(`${prefix}/role-bindings`),
      ]);
      setState({
        kind: "ready",
        data: {
          teams: teams.data.items,
          memberships: memberships.data.items,
          roles: roles.data.items,
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
    if (mutationError instanceof ApiError && mutationError.status === 412) {
      void load();
    }
  }

  async function createTeam(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("team");
    setError(null);
    try {
      const result = await api.post<Team>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/teams`,
        { name: String(form.get("name") ?? "").trim() },
        { "Idempotency-Key": crypto.randomUUID() },
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
    setError(null);
    try {
      const result = await api.post<Membership>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/memberships`,
        {
          principal_id: String(form.get("principal_id") ?? "").trim(),
          team_id: String(form.get("team_id") ?? "").trim() || null,
        },
        { "Idempotency-Key": crypto.randomUUID() },
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
    setError(null);
    try {
      const result = await api.post<RoleBinding>(
        `/v1/admin/tenants/${encodeURIComponent(tenantId)}/role-bindings`,
        {
          principal_id: String(form.get("principal_id") ?? "").trim(),
          role: String(form.get("role") ?? ""),
        },
        { "Idempotency-Key": crypto.randomUUID() },
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
    setError(null);
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
    setError(null);
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
    setError(null);
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
    setError(null);
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
      {error ? <InlineAlert message={error} /> : null}
      <div className="access-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">{t("Organization")}</span>
              <h2>{t("Teams")}</h2>
            </div>
            <button className="text-button" onClick={() => setModal("team")}>
              {t("New team")}
            </button>
          </div>
          {state.data.teams.length === 0 ? (
            <EmptyState title={t("No teams")} message={t("Create an optional team boundary.")} />
          ) : (
            <div className="record-list">
              {state.data.teams.map((team) => (
                <article key={team.id}>
                  <div>
                    <strong>{team.name}</strong>
                    <span className="mono">{team.id}</span>
                  </div>
                  <StatusPill status={team.status} />
                  <button
                    className="text-button"
                    disabled={busy === team.id}
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
            <button
              className="text-button"
              onClick={() => setModal("membership")}
            >
              {t("Add member")}
            </button>
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
                  <div>
                    <strong>{membership.principal_id}</strong>
                    <span>{membership.team_id ?? t("Tenant-wide")}</span>
                  </div>
                  <StatusPill status={membership.status} />
                  <div className="inline-actions">
                    <button
                      className="text-button"
                      disabled={busy === membership.id}
                      onClick={() => void toggleMembership(membership)}
                    >
                      {membership.status === "active" ? t("Disable") : t("Enable")}
                    </button>
                    <button
                      className="text-button danger-text"
                      disabled={busy === membership.id}
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
            <button className="text-button" onClick={() => setModal("role")}>
              {t("Bind role")}
            </button>
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
                  <div>
                    <strong>{binding.principal_id}</strong>
                    <span>{binding.role.replaceAll("_", " ")}</span>
                  </div>
                  <span className="mono">v{binding.version}</span>
                  <button
                    className="text-button danger-text"
                    disabled={busy === binding.id}
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
