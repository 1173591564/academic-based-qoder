import { ApiError } from "./api";

export type LoadFailure =
  | { kind: "denied"; message: string; requestId: string | null }
  | { kind: "unavailable"; message: string; requestId: string | null };

export function loadFailure(error: unknown): LoadFailure {
  if (error instanceof ApiError && error.status === 403) {
    return {
      kind: "denied",
      message: error.message,
      requestId: error.requestId,
    };
  }
  if (error instanceof ApiError) {
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

export function defaultTimeRange(): { from: string; to: string } {
  const to = new Date();
  const from = new Date(to.getTime() - 24 * 60 * 60 * 1000);
  return { from: from.toISOString(), to: to.toISOString() };
}

export function queryString(values: Record<string, string | null>): string {
  const parameters = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value) {
      parameters.set(key, value);
    }
  }
  return parameters.toString();
}

export function currentQueryValue(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name);
}

export function replaceQueryValue(name: string, value: string): void {
  const url = new URL(window.location.href);
  if (value) {
    url.searchParams.set(name, value);
  } else {
    url.searchParams.delete(name);
  }
  window.history.replaceState(
    {},
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
}
