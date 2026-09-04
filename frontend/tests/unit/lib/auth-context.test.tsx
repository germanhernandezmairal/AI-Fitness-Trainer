import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import * as apiClient from "@/lib/api-client";

function jsonResponse(status: number, body: unknown): Response {
  // 204 No Content responses cannot have a body
  if (status === 204) {
    return new Response(null, { status });
  }
  return new Response(JSON.stringify(body), { status });
}

describe("useAuth", () => {
  beforeEach(() => {
    localStorage.clear();
    apiClient.setTokens(null);
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts unauthenticated with no stored refresh token", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("becomes authenticated after a successful login", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(200, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login("me@example.com", "correct-horse-battery-staple");
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(apiClient.getAccessToken()).toBe("a1");
    expect(localStorage.getItem("refresh_token")).toBe("r1");
  });

  it("rejects with a user-friendly error on wrong password", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(401, { error: "Unauthorized" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await expect(
      act(async () => {
        await result.current.login("me@example.com", "wrong-password");
      }),
    ).rejects.toThrow("Invalid email or password");

    expect(result.current.isAuthenticated).toBe(false);
  });

  it("becomes authenticated after a successful register", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(201, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.register("me@example.com", "correct-horse-battery-staple", true);
    });

    expect(result.current.isAuthenticated).toBe(true);
  });

  it("sends the consent flag in the register request body", async () => {
    const fetchMock = vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(201, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.register("me@example.com", "correct-horse-battery-staple", true);
    });

    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init!.body as string);
    expect(body.consent).toBe(true);
  });

  it("clears tokens and flips to unauthenticated on logout", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }))
      .mockResolvedValueOnce(jsonResponse(204, {}));
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.login("me@example.com", "correct-horse-battery-staple");
    });

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(apiClient.getAccessToken()).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("becomes unauthenticated when apiFetch reports an auth failure", async () => {
    let registeredCallback: (() => void) | undefined;
    vi.spyOn(apiClient, "onAuthFailure").mockImplementation((callback) => {
      registeredCallback = callback;
    });
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse(200, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
    );
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.login("me@example.com", "correct-horse-battery-staple");
    });
    expect(result.current.isAuthenticated).toBe(true);
    expect(registeredCallback).toBeDefined();

    act(() => {
      // Simulate what api-client does internally when a retried request still 401s.
      registeredCallback?.();
    });

    expect(result.current.isAuthenticated).toBe(false);
  });
});
