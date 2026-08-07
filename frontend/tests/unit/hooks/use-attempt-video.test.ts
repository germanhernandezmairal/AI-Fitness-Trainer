import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAttemptVideo } from "@/hooks/use-attempt-video";

describe("useAttemptVideo", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:mock-url"),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns null while videoUrl is null", () => {
    const { result } = renderHook(() => useAttemptVideo(null));
    expect(result.current.blobUrl).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("fetches the video and exposes a blob URL", async () => {
    const blob = new Blob(["fake video bytes"], { type: "video/mp4" });
    vi.mocked(fetch).mockResolvedValueOnce(new Response(blob, { status: 200 }));

    const { result } = renderHook(() => useAttemptVideo("http://localhost:8000/v1/attempts/a1/video"));

    await waitFor(() => expect(result.current.blobUrl).toBe("blob:mock-url"));
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("reports an error when the fetch fails", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 502 }));

    const { result } = renderHook(() => useAttemptVideo("http://localhost:8000/v1/attempts/a1/video"));

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.blobUrl).toBeNull();
  });
});
