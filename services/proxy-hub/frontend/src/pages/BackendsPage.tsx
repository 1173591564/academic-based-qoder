import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";
import {
  EmptyState,
  InlineAlert,
  Modal,
  PageHeader,
  PanelState,
  ServerNotice,
  StatusPill,
  SubmitActions,
} from "../components";
import { loadFailure, type LoadFailure } from "../load";
import type {
  AdminMe,
  ListResponse,
  ResourceState,
  ScholarBackend,
} from "../types";

type BackendLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: ScholarBackend[] }
  | LoadFailure;

function backendResponse(backend: ScholarBackend): string {
  return `Server returned ${backend.name}, v${backend.version}, ${backend.status}; probe ${backend.probe.reason ?? "not observed"}.`;
}

export function BackendsPage({ me }: { me: AdminMe }) {
  const [state, setState] = useState<BackendLoad>({ kind: "loading" });
  const [selected, setSelected] =
    useState<ResourceState<ScholarBackend> | null>(null);
  const [selectedError, setSelectedError] = useState<string | null>(null);
  const [modal, setModal] = useState<"create" | "edit" | "rotate" | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const canManage = me.capabilities.includes("backend:manage");
  const canProbe = me.capabilities.includes("backend:probe");

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const result =
        await api.get<ListResponse<ScholarBackend>>("/v1/admin/backends");
      setState({ kind: "ready", data: result.data.items });
    } catch (error) {
      setState(loadFailure(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function selectBackend(backendId: string) {
    setSelected(null);
    setSelectedError(null);
    try {
      const result = await api.get<ScholarBackend>(
        `/v1/admin/backends/${encodeURIComponent(backendId)}`,
      );
      if (!result.etag) {
        throw new Error("The backend response did not include an ETag.");
      }
      setSelected({ data: result.data, etag: result.etag });
    } catch (error) {
      setSelectedError(
        error instanceof ApiError ? error.message : "Backend details unavailable.",
      );
    }
  }

  async function createBackend(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const result = await api.post<ScholarBackend>(
        "/v1/admin/backends",
        {
          name: String(form.get("name") ?? "").trim(),
          base_url: String(form.get("base_url") ?? "").trim(),
          corpus_version: String(form.get("corpus_version") ?? "").trim(),
          credential_ref: String(form.get("credential_ref") ?? "").trim(),
          credential_version:
            String(form.get("credential_version") ?? "").trim() || null,
        },
        { "Idempotency-Key": crypto.randomUUID() },
      );
      setModal(null);
      setNotice(backendResponse(result.data));
      await load();
      await selectBackend(result.data.id);
    } catch (error) {
      setSelectedError(
        error instanceof ApiError ? error.message : "Backend creation failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function mutateBackend(body: object, confirmation: string) {
    if (!selected || !window.confirm(confirmation)) {
      return;
    }
    setBusy(true);
    setSelectedError(null);
    try {
      const result = await api.patch<ScholarBackend>(
        `/v1/admin/backends/${encodeURIComponent(selected.data.id)}`,
        body,
        selected.etag,
      );
      if (!result.etag) {
        throw new Error("The backend mutation did not include an ETag.");
      }
      setSelected({ data: result.data, etag: result.etag });
      setNotice(backendResponse(result.data));
      await load();
    } catch (error) {
      setSelectedError(
        error instanceof ApiError ? error.message : "Backend update failed.",
      );
      if (error instanceof ApiError && error.status === 412) {
        await selectBackend(selected.data.id);
      }
    } finally {
      setBusy(false);
    }
  }

  async function editBackend(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) {
      return;
    }
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setSelectedError(null);
    try {
      const result = await api.patch<ScholarBackend>(
        `/v1/admin/backends/${encodeURIComponent(selected.data.id)}`,
        {
          name: String(form.get("name") ?? "").trim(),
          base_url: String(form.get("base_url") ?? "").trim(),
          corpus_version: String(form.get("corpus_version") ?? "").trim(),
        },
        selected.etag,
      );
      if (!result.etag) {
        throw new Error("The backend mutation did not include an ETag.");
      }
      setSelected({ data: result.data, etag: result.etag });
      setModal(null);
      setNotice(backendResponse(result.data));
      await load();
    } catch (error) {
      setSelectedError(
        error instanceof ApiError ? error.message : "Backend update failed.",
      );
      if (error instanceof ApiError && error.status === 412) {
        await selectBackend(selected.data.id);
      }
    } finally {
      setBusy(false);
    }
  }

  async function rotateCredential(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !window.confirm("Rotate the backend credential reference?")) {
      return;
    }
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const result = await api.post<ScholarBackend>(
        `/v1/admin/backends/${encodeURIComponent(selected.data.id)}:rotate-credential`,
        {
          credential_ref: String(form.get("credential_ref") ?? "").trim(),
          credential_version:
            String(form.get("credential_version") ?? "").trim() || null,
        },
        { "If-Match": selected.etag },
      );
      if (!result.etag) {
        throw new Error("The rotation response did not include an ETag.");
      }
      setSelected({ data: result.data, etag: result.etag });
      setModal(null);
      setNotice(backendResponse(result.data));
      await load();
    } catch (error) {
      setSelectedError(
        error instanceof ApiError ? error.message : "Credential rotation failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function probeBackend() {
    if (!selected) {
      return;
    }
    setBusy(true);
    setSelectedError(null);
    try {
      const result = await api.post<ScholarBackend>(
        `/v1/admin/backends/${encodeURIComponent(selected.data.id)}:probe`,
        {},
      );
      if (!result.etag) {
        throw new Error("The probe response did not include an ETag.");
      }
      setSelected({ data: result.data, etag: result.etag });
      setNotice(backendResponse(result.data));
      await load();
    } catch (error) {
      setSelectedError(
        error instanceof ApiError ? error.message : "Backend probe failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Scholar routing"
        title="Backend registry"
        description="Register Scholar services, verify readiness, and rotate deployer-owned credential references."
        action={
          canManage
            ? { label: "Register backend", onClick: () => setModal("create") }
            : undefined
        }
      />
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {selectedError ? <InlineAlert message={selectedError} /> : null}
      {state.kind === "loading" ? (
        <section className="panel">
          <PanelState kind="loading" />
        </section>
      ) : state.kind === "denied" || state.kind === "unavailable" ? (
        <section className="panel">
          <PanelState
            kind={state.kind}
            message={state.message}
            requestId={state.requestId}
            onRetry={() => void load()}
          />
        </section>
      ) : state.data.length === 0 ? (
        <section className="panel">
          <EmptyState
            title="No Scholar backends"
            message="Register a backend before configuring tenant routes."
          />
        </section>
      ) : (
        <div className={selected ? "split-layout wide-detail" : undefined}>
          <section className="panel">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Backend</th>
                    <th>Status</th>
                    <th>Probe</th>
                    <th>Corpus</th>
                  </tr>
                </thead>
                <tbody>
                  {state.data.map((backend) => (
                    <tr
                      key={backend.id}
                      className={
                        selected?.data.id === backend.id ? "selected" : undefined
                      }
                      onClick={() => void selectBackend(backend.id)}
                    >
                      <td>
                        <strong>{backend.name}</strong>
                        <span>{backend.base_url}</span>
                      </td>
                      <td>
                        <StatusPill status={backend.status} />
                      </td>
                      <td>{backend.probe.reason ?? "Not probed"}</td>
                      <td className="mono">{backend.corpus_version}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {selected ? (
            <aside className="detail-panel backend-detail">
              <button
                className="close-button"
                aria-label="Close backend details"
                onClick={() => setSelected(null)}
              >
                ×
              </button>
              <span className="eyebrow">Backend detail</span>
              <h2>{selected.data.name}</h2>
              <StatusPill
                status={selected.data.probe.ready ? "ready" : selected.data.status}
              />
              <dl>
                <div>
                  <dt>Service URL</dt>
                  <dd>{selected.data.base_url}</dd>
                </div>
                <div>
                  <dt>Corpus</dt>
                  <dd className="mono">{selected.data.corpus_version}</dd>
                </div>
                <div>
                  <dt>Credential version</dt>
                  <dd>{selected.data.credential.version ?? "Unversioned"}</dd>
                </div>
                <div>
                  <dt>Probe</dt>
                  <dd>
                    {selected.data.probe.reason ?? "Not probed"} ·{" "}
                    {selected.data.probe.observed_at
                      ? new Date(
                          selected.data.probe.observed_at,
                        ).toLocaleString()
                      : "never"}
                  </dd>
                </div>
              </dl>
              <div className="button-stack">
                {canProbe ? (
                  <button
                    className="secondary-button"
                    disabled={busy}
                    onClick={() => void probeBackend()}
                  >
                    Probe readiness
                  </button>
                ) : null}
                {canManage ? (
                  <>
                    <button
                      className="secondary-button"
                      onClick={() => setModal("edit")}
                    >
                      Edit registration
                    </button>
                    <button
                      className="secondary-button"
                      onClick={() => setModal("rotate")}
                    >
                      Rotate credential reference
                    </button>
                    <button
                      className={
                        selected.data.status === "active"
                          ? "danger-button"
                          : "primary-button"
                      }
                      disabled={busy}
                      onClick={() =>
                        void mutateBackend(
                          {
                            status:
                              selected.data.status === "active"
                                ? "disabled"
                                : "active",
                          },
                          `${selected.data.status === "active" ? "Disable" : "Activate"} this backend?`,
                        )
                      }
                    >
                      {selected.data.status === "active"
                        ? "Disable backend"
                        : "Activate backend"}
                    </button>
                  </>
                ) : null}
              </div>
            </aside>
          ) : null}
        </div>
      )}
      {modal === "create" ? (
        <Modal
          title="Register Scholar backend"
          description="Only env:NAME credential references are accepted. Secret material stays outside the Hub database."
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void createBackend(event)}>
            <label>
              Display name
              <input name="name" required maxLength={200} autoFocus />
            </label>
            <label>
              HTTPS base URL
              <input
                name="base_url"
                required
                type="url"
                placeholder="https://scholar.internal"
              />
            </label>
            <label>
              Corpus version
              <input name="corpus_version" required maxLength={128} />
            </label>
            <label>
              Credential reference
              <input
                name="credential_ref"
                required
                pattern="env:[A-Z][A-Z0-9_]*"
                placeholder="env:SCHOLAR_SERVICE_TOKEN"
              />
            </label>
            <label>
              Credential version
              <input name="credential_version" maxLength={128} />
            </label>
            <SubmitActions
              busy={busy}
              submitLabel="Register backend"
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
      {modal === "rotate" && selected ? (
        <Modal
          title="Rotate credential reference"
          description="The existing readiness result will be invalidated until the backend is probed again."
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void rotateCredential(event)}>
            <label>
              New credential reference
              <input
                name="credential_ref"
                required
                pattern="env:[A-Z][A-Z0-9_]*"
                placeholder="env:SCHOLAR_SERVICE_TOKEN_V2"
                autoFocus
              />
            </label>
            <label>
              Credential version
              <input name="credential_version" maxLength={128} />
            </label>
            <SubmitActions
              busy={busy}
              submitLabel="Rotate reference"
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
      {modal === "edit" && selected ? (
        <Modal
          title="Edit backend registration"
          description="Changing service or corpus identity invalidates the previous readiness result."
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void editBackend(event)}>
            <label>
              Display name
              <input
                name="name"
                required
                maxLength={200}
                defaultValue={selected.data.name}
                autoFocus
              />
            </label>
            <label>
              HTTPS base URL
              <input
                name="base_url"
                required
                type="url"
                defaultValue={selected.data.base_url}
              />
            </label>
            <label>
              Corpus version
              <input
                name="corpus_version"
                required
                maxLength={128}
                defaultValue={selected.data.corpus_version}
              />
            </label>
            <SubmitActions
              busy={busy}
              submitLabel="Save registration"
              onCancel={() => setModal(null)}
            />
          </form>
        </Modal>
      ) : null}
    </>
  );
}
