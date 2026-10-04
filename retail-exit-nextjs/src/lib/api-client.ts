/**
 * SEC-OPS V8 Universal API Client
 * Robust, fault-tolerant HTTP client for FastAPI backend interactions.
 * Prevents unhandled fetch crashes when backend is restarting or under load.
 */

export const API_BASE = 
  typeof window !== "undefined"
    ? "" // Client-side uses Next.js rewrites /api/... directly to avoid CORS
    : process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export function getWsUrl(path: string = "/ws/live"): string {
  if (typeof window === "undefined") return `ws://127.0.0.1:8000${path}`;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // Use port 8000 directly for WebSockets or current host if reverse proxied
  return `${proto}//${window.location.hostname}:8000${path}`;
}

export async function safeFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const isAbsolute = path.startsWith("http://") || path.startsWith("https://");
  const url = isAbsolute ? path : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Accept": "application/json",
        ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
    return res;
  } catch (error) {
    console.warn(`[SEC-OPS API] safeFetch network exception on ${url}:`, error);
    // Return a safe synthetic Response to prevent unhandled rejection crashes
    return new Response(
      JSON.stringify({
        status: "OFFLINE",
        message: "Backend service unreachable",
        error: String(error),
      }),
      {
        status: 503,
        statusText: "Service Unavailable",
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}

export async function apiGet<T = any>(path: string, fallback: T = [] as any): Promise<T> {
  try {
    const res = await safeFetch(path);
    if (!res.ok) {
      console.warn(`[SEC-OPS API] apiGet failed with status ${res.status} on ${path}`);
      return fallback;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`[SEC-OPS API] apiGet JSON parse error on ${path}:`, err);
    return fallback;
  }
}

export function formatErrorMessage(error: any): string {
  if (!error) return "Unknown error occurred";
  if (typeof error === "string") return error;
  if (Array.isArray(error)) {
    return error
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const loc = Array.isArray(item.loc) ? item.loc.filter(Boolean).join(" -> ") : "";
          const msg = item.msg || item.message || JSON.stringify(item);
          return loc ? `${loc}: ${msg}` : String(msg);
        }
        return String(item);
      })
      .join("; ");
  }
  if (typeof error === "object") {
    if (error.msg) return String(error.msg);
    if (error.message) return String(error.message);
    if (error.detail) return formatErrorMessage(error.detail);
    try {
      return JSON.stringify(error);
    } catch {
      return String(error);
    }
  }
  return String(error);
}

export async function apiPost<T = any>(path: string, payload?: any): Promise<{ ok: boolean; status: number; data?: T; error?: string }> {
  try {
    const isFormData = payload instanceof FormData;
    const res = await safeFetch(path, {
      method: "POST",
      body: isFormData ? payload : (payload !== undefined ? JSON.stringify(payload) : undefined),
    });
    
    let data;
    try {
      data = await res.json();
    } catch {
      data = null;
    }

    return {
      ok: res.ok,
      status: res.status,
      data,
      error: !res.ok ? formatErrorMessage(data?.detail || data?.message || res.statusText) : undefined,
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 503,
      error: formatErrorMessage(err?.message || "Network error"),
    };
  }
}

export async function apiPut<T = any>(path: string, payload?: any): Promise<{ ok: boolean; status: number; data?: T; error?: string }> {
  try {
    const res = await safeFetch(path, {
      method: "PUT",
      body: payload !== undefined ? JSON.stringify(payload) : undefined,
    });
    let data;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    return {
      ok: res.ok,
      status: res.status,
      data,
      error: !res.ok ? formatErrorMessage(data?.detail || data?.message || res.statusText) : undefined,
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 503,
      error: formatErrorMessage(err?.message || "Network error"),
    };
  }
}

export async function apiDelete<T = any>(path: string): Promise<{ ok: boolean; status: number; data?: T; error?: string }> {
  try {
    const res = await safeFetch(path, { method: "DELETE" });
    let data;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    return {
      ok: res.ok,
      status: res.status,
      data,
      error: !res.ok ? formatErrorMessage(data?.detail || data?.message || res.statusText) : undefined,
    };
  } catch (err: any) {
    return {
      ok: false,
      status: 503,
      error: formatErrorMessage(err?.message || "Network error"),
    };
  }
}
