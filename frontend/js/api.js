const API_URL = window.RECON_API_URL || "/api";
localStorage.removeItem("token");

class ApiError extends Error {
    constructor(message, status = 0, requestId = null) {
        super(message);
        this.status = status;
        this.requestId = requestId;
    }
}

function csrfCookie() {
    const entry = document.cookie.split("; ").find(value =>
        value.startsWith("__Host-recon_csrf=") || value.startsWith("recon_csrf="));
    return entry ? decodeURIComponent(entry.substring(entry.indexOf("=") + 1)) : "";
}

let csrfRequest;
async function ensureCsrf() {
    const existing = csrfCookie();
    const age = Date.now() / 1000 - Number(existing.split(".")[0]);
    if (existing && age >= 0 && age < 3300) return existing;
    if (!csrfRequest) {
        csrfRequest = api("/auth/csrf").then(data => data.csrf_token).finally(() => { csrfRequest = null; });
    }
    return csrfRequest;
}

function handleExpiredSession() {
    const page = location.pathname.split("/").pop();
    if (!["", "index.html", "login.html", "register.html", "forgot-password.html", "reset-password.html"].includes(page)) {
        location.replace("login.html?expired=1");
    }
}

async function api(endpoint, method = "GET", body = null, config = {}) {
    method = method.toUpperCase();
    const safe = ["GET", "HEAD"].includes(method);
    const headers = {};
    if (!safe) headers["X-CSRF-Token"] = await ensureCsrf();
    const options = {method, headers, credentials: "same-origin"};
    if (body instanceof FormData) options.body = body;
    else if (body !== null) {
        headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }
    // Never automatically replay a mutation.
    const attempts = safe ? 3 : 1;
    for (let attempt = 0; attempt < attempts; attempt++) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), config.timeoutMs || 30000);
        let retryDelay = Math.min(4000, 500 * (2 ** attempt) + Math.random() * 250);
        try {
            const response = await fetch(API_URL + endpoint, {...options, signal: controller.signal});
            if (safe && [429, 502, 503, 504].includes(response.status) && attempt < attempts - 1) {
                const retryAfter = Number(response.headers.get("Retry-After"));
                if (Number.isFinite(retryAfter) && retryAfter > 0) retryDelay = Math.min(30000, retryAfter * 1000);
                if (response.body) await response.body.cancel();
            } else {
                if (response.ok && config.blob) return await response.blob();
                const type = response.headers.get("content-type") || "";
                let data;
                try {
                    data = type.includes("application/json") || type.includes("+json")
                        ? await response.json() : await response.text();
                } catch {
                    throw new ApiError("The server returned an unreadable response. Try again.", response.status);
                }
                if (!response.ok) {
                    if (response.status === 401 && endpoint !== "/auth/login") handleExpiredSession();
                    const message = typeof data === "object" && data ? data.detail || data.title : null;
                    throw new ApiError(typeof message === "string" ? message : `Request failed (${response.status}). Please try again.`,
                        response.status, response.headers.get("X-Request-Id"));
                }
                return data;
            }
        } catch (error) {
            if (error instanceof ApiError) throw error;
            if (!safe || attempt === attempts - 1) {
                throw new ApiError(error.name === "AbortError"
                    ? "The request timed out. Check its status before trying again."
                    : "Cannot connect. Check your connection and try again.");
            }
        } finally {
            clearTimeout(timeout);
        }
        await new Promise(resolve => setTimeout(resolve, retryDelay));
    }
}
