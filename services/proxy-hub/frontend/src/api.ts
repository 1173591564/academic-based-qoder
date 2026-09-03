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

export async function request<T>(
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
  const data =
    response.status === 204 ? (undefined as T) : ((await response.json()) as T);
  return { data, etag: response.headers.get("ETag") };
}

export function mutationHeaders(
  cookieHeader: string,
  extraHeaders: Record<string, string> = {},
): Record<string, string> {
  const csrf = getCookie(cookieHeader, "proxy_hub_csrf");
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
    ...extraHeaders,
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
      headers: mutationHeaders(document.cookie, extraHeaders),
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
      headers: mutationHeaders(document.cookie, { "If-Match": etag }),
      body: JSON.stringify(body),
    });
  },

  put<T>(path: string, body: object, etag: string): Promise<ApiResult<T>> {
    return request<T>(path, {
      method: "PUT",
      headers: mutationHeaders(document.cookie, { "If-Match": etag }),
      body: JSON.stringify(body),
    });
  },

  delete(path: string, etag: string): Promise<ApiResult<void>> {
    return request<void>(path, {
      method: "DELETE",
      headers: mutationHeaders(document.cookie, { "If-Match": etag }),
    });
  },
};
