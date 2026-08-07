import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { VideoUploadForm } from "@/components/video-upload-form";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function makeFile(name: string, sizeBytes: number, type: string): File {
  const file = new File([new Uint8Array(sizeBytes)], name, { type });
  return file;
}

// Helper to upload a file to an input element in jsdom
function uploadFileToInput(input: HTMLInputElement, file: File): void {
  const fileList = {
    0: file,
    length: 1,
    item: (index: number) => (index === 0 ? file : null),
  } as unknown as FileList;

  Object.defineProperty(input, "files", {
    value: fileList,
    writable: false,
  });

  const event = new Event("change", { bubbles: true });
  input.dispatchEvent(event);
}

describe("VideoUploadForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("rejects an unsupported extension before uploading", async () => {
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />, { wrapper });
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i) as HTMLInputElement;
    const file = makeFile("clip.avi", 1000, "video/x-msvideo");
    uploadFileToInput(input, file);

    await user.click(screen.getByRole("button", { name: /upload/i }));

    expect(await screen.findByText(/mp4 or mov/i)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects a file over 100MB before uploading", async () => {
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />, { wrapper });
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i) as HTMLInputElement;
    const file = makeFile("clip.mp4", 105_000_000, "video/mp4");
    uploadFileToInput(input, file);

    await user.click(screen.getByRole("button", { name: /upload/i }));

    expect(await screen.findByText(/100 mb/i)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("uploads a valid file and calls onUploaded with the new attempt id", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ attempt_id: "attempt-1", status: "queued" }), { status: 202 }),
    );
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />, { wrapper });
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i) as HTMLInputElement;
    const file = makeFile("clip.mp4", 1000, "video/mp4");
    uploadFileToInput(input, file);

    await user.click(screen.getByRole("button", { name: /upload/i }));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith("attempt-1"));
  });

  it("shows the backend's rejection message on a 400 response", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({ error: { code: "video_too_long", message: "too long" } }),
        { status: 400 },
      ),
    );
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />, { wrapper });
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i) as HTMLInputElement;
    const file = makeFile("clip.mp4", 1000, "video/mp4");
    uploadFileToInput(input, file);

    await user.click(screen.getByRole("button", { name: /upload/i }));

    expect(await screen.findByText(/60 seconds/i)).toBeInTheDocument();
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it("shows an error message on network failure", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("network error"));
    const onUploaded = vi.fn();
    render(<VideoUploadForm onUploaded={onUploaded} />, { wrapper });
    const user = userEvent.setup();

    const input = screen.getByLabelText(/video file/i) as HTMLInputElement;
    const file = makeFile("clip.mp4", 1000, "video/mp4");
    uploadFileToInput(input, file);

    await user.click(screen.getByRole("button", { name: /upload/i }));

    expect(await screen.findByText(/could not upload the video/i)).toBeInTheDocument();
    expect(onUploaded).not.toHaveBeenCalled();
  });
});
