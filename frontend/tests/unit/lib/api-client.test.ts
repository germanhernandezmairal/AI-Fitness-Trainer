import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, AuthError, getAccessToken, onAuthFailure, setTokens } from "@/lib/api-client";

const BASE_URL = "http://localhost:8000";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch", () => {
  beforeEach(() => {
    setTokens(null);
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the access token as a Bearer header", async () => {
    setTokens({ access_token: "abc123", refresh_token: "r1", token_type: "bearer" });
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    await apiFetch("/v1/attempts");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init?.headers as Record<string, string>)["Authorization"]).toBe("Bearer abc123");
  });

  it("returns non-401 responses untouched, without retrying", async () => {
    setTokens({ access_token: "abc123", refresh_token: "r1", token_type: "bearer" });
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(400, { error: { code: "file_too_large" } }));

    const response = await apiFetch("/v1/attempts", { method: "POST" });

    expect(response.status).toBe(400);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("on a 401, refreshes once and retries the original request", async () => {
    setTokens({ access_token: "expired", refresh_token: "good-refresh", token_type: "bearer" });
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, {})) // original request
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "fresh", refresh_token: "rotated", token_type: "bearer" }),
      ) // POST /v1/auth/refresh
      .mockResolvedValueOnce(jsonResponse(200, { ok: true })); // retried original request

    const response = await apiFetch("/v1/attempts");

    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledTimes(3);
    const refreshCall = vi.mocked(fetch).mock.calls[1];
    expect(refreshCall[0]).toBe(`${BASE_URL}/v1/auth/refresh`);
    expect(getAccessToken()).toBe("fresh");
    const retryCall = vi.mocked(fetch).mock.calls[2];
    expect((retryCall[1]?.headers as Record<string, string>)["Authorization"]).toBe("Bearer fresh");
  });

  it("throws AuthError and fires onAuthFailure when refresh itself fails", async () => {
    const failureHandler = vi.fn();
    onAuthFailure(failureHandler);
    setTokens({ access_token: "expired", refresh_token: "bad-refresh", token_type: "bearer" });
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, {})) // original request
      .mockResolvedValueOnce(jsonResponse(401, {})); // POST /v1/auth/refresh also fails

    await expect(apiFetch("/v1/attempts")).rejects.toThrow(AuthError);
    expect(failureHandler).toHaveBeenCalledOnce();
    expect(getAccessToken()).toBeNull();
  });

  it("throws AuthError without retrying again when the retried request itself 401s", async () => {
    setTokens({ access_token: "expired", refresh_token: "good-refresh", token_type: "bearer" });
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, {})) // original request
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "fresh", refresh_token: "rotated", token_type: "bearer" }),
      ) // refresh succeeds
      .mockResolvedValueOnce(jsonResponse(401, {})); // retried request still 401s

    await expect(apiFetch("/v1/attempts")).rejects.toThrow(AuthError);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("deduplicates concurrent refresh attempts to prevent token-reuse detection", async () => {
    setTokens({ access_token: "expired", refresh_token: "good-refresh", token_type: "bearer" });
    // Mock sequence for two concurrent calls: both 401, one refresh, both retries succeed
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, {})) // call 1 original request
      .mockResolvedValueOnce(jsonResponse(401, {})) // call 2 original request
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "fresh", refresh_token: "rotated", token_type: "bearer" }),
      ) // shared refresh (only called once)
      .mockResolvedValueOnce(jsonResponse(200, { ok: true })) // call 1 retry
      .mockResolvedValueOnce(jsonResponse(200, { ok: true })); // call 2 retry

    // Fire two concurrent calls that both 401
    const result = await Promise.all([apiFetch("/v1/attempts"), apiFetch("/v1/other")]);

    // Both should succeed after the shared refresh
    expect(result[0].status).toBe(200);
    expect(result[1].status).toBe(200);
    // Refresh endpoint should be called exactly once despite two 401s
    const refreshCalls = vi.mocked(fetch).mock.calls.filter((call) => call[0] === `${BASE_URL}/v1/auth/refresh`);
    expect(refreshCalls).toHaveLength(1);
  });
});
