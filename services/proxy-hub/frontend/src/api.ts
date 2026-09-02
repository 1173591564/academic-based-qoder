interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
}

export interface ApiResult<T> {
  data: T;
  etag: string | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export function getCookie(cookieHeader: string, name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  for (const part of cookieHeader.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix)) {
      return decodeURIComponent(value.slice(prefix.length));
    }
  }
  return null;
}

async function parseError(response: Response): Promise<ApiError> {
  let envelope: ErrorEnvelope = {};
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    envelope = {};
  }
  return new ApiError(
    response.status,
    envelope.error?.code ?? "request_failed",
    envelope.error?.message ?? "The request could not be completed.",
    envelope.error?.request_id ?? response.headers.get("X-Request-ID"),
  );
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  const data = (await response.json()) as T;
  return { data, etag: response.headers.get("ETag") };
}

function mutationHeaders(): Record<string, string> {
  const csrf = getCookie(document.cookie, "proxy_hub_csrf");
  if (!csrf) {
    throw new ApiError(
      403,
      "csrf_unavailable",
      "The browser session must be refreshed before making changes.",
      null,
    );
  }
  return {
    "Content-Type": "application/json",
    "X-CSRF-Token": csrf,
  };
}

export const api = {
  get<T>(path: string): Promise<ApiResult<T>> {
    return request<T>(path);
  },

  post<T>(
    path: string,
    body: object,
    extraHeaders: Record<string, string> = {},
  ): Promise<ApiResult<T>> {
    return request<T>(path, {
      method: "POST",
      headers: { ...mutationHeaders(), ...extraHeaders },
      body: JSON.stringify(body),
    });
  },

  patch<T>(
    path: string,
    body: object,
    etag: string,
  ): Promise<ApiResult<T>> {
    return request<T>(path, {
      method: "PATCH",
      headers: { ...mutationHeaders(), "If-Match": etag },
      body: JSON.stringify(body),
    });
  },
};
