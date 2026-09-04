import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError, idempotencyKey } from "../api";
import {
  EmptyState,
  InlineAlert,
  ListToolbar,
  Modal,
  PageHeader,
  PanelState,
  ServerNotice,
  StatusPill,
  SubmitActions,
} from "../components";
import { useI18n } from "../i18n";
import { loadFailure, type LoadFailure } from "../load";
import type { ListResponse, ScholarToken } from "../types";

type TokenLoad =
  | { kind: "loading" }
  | { kind: "ready"; data: ScholarToken[] }
  | LoadFailure;

type TokenModal =
  | { kind: "create" }
  | { kind: "rename"; token: ScholarToken }
  | { kind: "rotate"; token: ScholarToken }
  | null;

function tokenIdentity(token: ScholarToken): string {
  return `${token.token_prefix}••••${token.token_last_four}`;
}

export function TokensPage() {
  const { t } = useI18n();
  const [state, setState] = useState<TokenLoad>({ kind: "loading" });
  const [modal, setModal] = useState<TokenModal>(null);
  const [issuedToken, setIssuedToken] = useState<ScholarToken | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const result = await api.get<ListResponse<ScholarToken>>(
        "/v1/admin/tokens",
      );
      setState({ kind: "ready", data: result.data.items });
    } catch (loadError) {
      setState(loadFailure(loadError));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredTokens = useMemo(() => {
    if (state.kind !== "ready") {
      return [];
    }
    const query = search.trim().toLocaleLowerCase();
    if (!query) {
      return state.data;
    }
    return state.data.filter((token) =>
      [token.name, token.token_prefix, token.token_last_four, token.status].some(
        (value) => value.toLocaleLowerCase().includes(query),
      ),
    );
  }, [search, state]);

  function mutationFailed(mutationError: unknown, fallback: string): void {
    setError(
      mutationError instanceof ApiError ? mutationError.message : fallback,
    );
    setRequestId(
      mutationError instanceof ApiError ? mutationError.requestId : null,
    );
    if (mutationError instanceof ApiError && mutationError.status === 412) {
      void load();
    }
  }

  async function createToken(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim().normalize("NFKC");
    if (
      state.kind === "ready" &&
      state.data.some(
        (token) => token.name.toLocaleLowerCase() === name.toLocaleLowerCase(),
      )
    ) {
      setError(t("A Token with this name already exists."));
      return;
    }
    setBusy("create");
    setError(null);
    try {
      const result = await api.post<ScholarToken>(
        "/v1/admin/tokens",
        { name },
        { "Idempotency-Key": idempotencyKey() },
      );
      setModal(null);
      setIssuedToken(result.data);
      setCopied(false);
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Token creation failed."));
    } finally {
      setBusy(null);
    }
  }

  async function renameToken(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (modal?.kind !== "rename") {
      return;
    }
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim().normalize("NFKC");
    setBusy(modal.token.id);
    setError(null);
    try {
      await api.patch<ScholarToken>(
        `/v1/admin/tokens/${encodeURIComponent(modal.token.id)}`,
        { name },
        modal.token.etag,
      );
      setModal(null);
      setNotice(t("Token name updated."));
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Token rename failed."));
    } finally {
      setBusy(null);
    }
  }

  async function rotateToken(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (modal?.kind !== "rotate") {
      return;
    }
    const form = new FormData(event.currentTarget);
    if (form.get("confirm") !== "yes") {
      setError(t("Confirm that the current Token will stop working."));
      return;
    }
    setBusy(modal.token.id);
    setError(null);
    try {
      const result = await api.post<ScholarToken>(
        `/v1/admin/tokens/${encodeURIComponent(modal.token.id)}/rotate`,
        { confirm: true },
        { "Idempotency-Key": idempotencyKey() },
      );
      setModal(null);
      setIssuedToken(result.data);
      setCopied(false);
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Token rotation failed."));
    } finally {
      setBusy(null);
    }
  }

  async function revokeToken(token: ScholarToken) {
    if (!window.confirm(t("Revoke this Token immediately?"))) {
      return;
    }
    setBusy(token.id);
    setError(null);
    try {
      await api.post<void>(
        `/v1/admin/tokens/${encodeURIComponent(token.id)}/revoke`,
        {},
        { "If-Match": token.etag },
      );
      setNotice(t("Token revoked."));
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Token revocation failed."));
    } finally {
      setBusy(null);
    }
  }

  async function deleteToken(token: ScholarToken) {
    if (
      !window.confirm(
        t("Delete this Token and disable its managed identity? Audit history is retained."),
      )
    ) {
      return;
    }
    setBusy(token.id);
    setError(null);
    try {
      await api.delete(
        `/v1/admin/tokens/${encodeURIComponent(token.id)}`,
        token.etag,
      );
      setNotice(t("Token deleted. Audit history was retained."));
      await load();
    } catch (mutationError) {
      mutationFailed(mutationError, t("Token deletion failed."));
    } finally {
      setBusy(null);
    }
  }

  async function copyIssuedToken() {
    if (!issuedToken?.token) {
      return;
    }
    try {
      await navigator.clipboard.writeText(issuedToken.token);
      setCopied(true);
      setNotice(t("Token copied."));
    } catch {
      setError(t("Copy failed. Select and copy the Token manually."));
    }
  }

  function closeIssuedToken() {
    if (
      !copied &&
      !window.confirm(
        t("This Token has not been copied. Close it permanently anyway?"),
      )
    ) {
      return;
    }
    setIssuedToken(null);
  }

  return (
    <>
      <PageHeader
        eyebrow={t("SCHOLAR ACCESS")}
        title={t("Token management")}
        description={t(
          "Create one permanent Token per name. Full Token values are shown once.",
        )}
        action={{ label: t("Create Token"), onClick: () => setModal({ kind: "create" }) }}
      />
      {notice ? (
        <ServerNotice message={notice} onClose={() => setNotice(null)} />
      ) : null}
      {error ? <InlineAlert message={error} requestId={requestId} /> : null}
      <section className="panel">
        {state.kind === "loading" ? (
          <PanelState kind="loading" />
        ) : state.kind === "denied" || state.kind === "unavailable" ? (
          <PanelState
            kind={state.kind}
            message={state.message}
            requestId={state.requestId}
            onRetry={() => void load()}
          />
        ) : state.data.length === 0 ? (
          <EmptyState
            title={t("No Tokens")}
            message={t("Create a Token to connect DSH Scholar mode.")}
            action={{ label: t("Create Token"), onClick: () => setModal({ kind: "create" }) }}
          />
        ) : (
          <>
            <ListToolbar
              value={search}
              onChange={setSearch}
              label={t("Search Tokens")}
              placeholder={t("Search by Token name or prefix")}
              resultCount={filteredTokens.length}
              totalCount={state.data.length}
            />
            <div className="table-wrap">
              <table className="responsive-table token-table">
                <thead>
                  <tr>
                    <th>{t("Token name")}</th>
                    <th>{t("Token")}</th>
                    <th>{t("Status")}</th>
                    <th>{t("Created")}</th>
                    <th>{t("Last used")}</th>
                    <th>{t("Actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTokens.map((token) => (
                    <tr key={token.id}>
                      <td data-label={t("Token name")}><strong>{token.name}</strong></td>
                      <td className="mono" data-label={t("Token")}>{tokenIdentity(token)}</td>
                      <td data-label={t("Status")}><StatusPill status={token.status} /></td>
                      <td data-label={t("Created")}>{new Date(token.created_at).toLocaleString()}</td>
                      <td data-label={t("Last used")}>
                        {token.last_used_at
                          ? new Date(token.last_used_at).toLocaleString()
                          : t("Never used")}
                      </td>
                      <td data-label={t("Actions")}>
                        <div className="row-actions">
                          <button type="button" className="text-button" onClick={() => setModal({ kind: "rename", token })}>{t("Rename")}</button>
                          <button type="button" className="text-button" disabled={busy === token.id} onClick={() => setModal({ kind: "rotate", token })}>{t("Rotate Token")}</button>
                          {token.status === "active" ? (
                            <button type="button" className="text-button danger" disabled={busy === token.id} onClick={() => void revokeToken(token)}>{t("Revoke Token")}</button>
                          ) : null}
                          <button type="button" className="text-button danger" disabled={busy === token.id} onClick={() => void deleteToken(token)}>{t("Delete")}</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {modal?.kind === "create" ? (
        <Modal
          title={t("Create Token")}
          description={t("The Token is permanent until it is revoked or rotated.")}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void createToken(event)}>
            <label>
              {t("Token name")}
              <input name="name" required maxLength={200} autoComplete="off" placeholder={t("Example: Literature group")} />
            </label>
            <SubmitActions busy={busy === "create"} submitLabel={t("Create Token")} onCancel={() => setModal(null)} />
          </form>
        </Modal>
      ) : null}

      {modal?.kind === "rename" ? (
        <Modal
          title={t("Rename Token")}
          description={t("Renaming does not change the Token secret.")}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void renameToken(event)}>
            <label>
              {t("Token name")}
              <input name="name" required maxLength={200} defaultValue={modal.token.name} autoComplete="off" />
            </label>
            <SubmitActions busy={busy === modal.token.id} submitLabel={t("Save name")} onCancel={() => setModal(null)} />
          </form>
        </Modal>
      ) : null}

      {modal?.kind === "rotate" ? (
        <Modal
          title={t("Rotate Token")}
          description={t("The current Token stops working immediately. The replacement is shown once.")}
          onClose={() => setModal(null)}
        >
          <form onSubmit={(event) => void rotateToken(event)}>
            <label className="confirmation-field">
              <input type="checkbox" name="confirm" value="yes" />
              <span>{t("I understand that the current Token will be revoked.")}</span>
            </label>
            <SubmitActions busy={busy === modal.token.id} submitLabel={t("Rotate Token")} onCancel={() => setModal(null)} />
          </form>
        </Modal>
      ) : null}

      {issuedToken?.token ? (
        <Modal
          title={t("Save this Token now")}
          description={t("Proxy Hub stores only a digest. This full Token cannot be shown again.")}
          onClose={closeIssuedToken}
        >
          <div className="secret-display">
            <code>{issuedToken.token}</code>
          </div>
          <div className="modal-actions">
            <button type="button" className="secondary-button" onClick={() => void copyIssuedToken()}>
              {copied ? t("Copied") : t("Copy Token")}
            </button>
            <button type="button" className="primary-button" onClick={closeIssuedToken}>
              {t("I saved it")}
            </button>
          </div>
        </Modal>
      ) : null}
    </>
  );
}
