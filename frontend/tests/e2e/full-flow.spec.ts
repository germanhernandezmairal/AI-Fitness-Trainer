// frontend/tests/e2e/full-flow.spec.ts
import { test, expect } from "@playwright/test";
import path from "path";

const VIDEO_PATH = path.resolve(__dirname, "../../../backend/tests/fixtures/squat.mp4");

test("register, log out, log back in, upload, see a result, and delete it", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";

  await page.goto("/register");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByLabel(/i agree/i).check();
  await page.getByRole("button", { name: /create account/i }).click();

  await expect(page).toHaveURL("/");

  // Exercise the real login page against the real backend: log out, then log
  // back in with the same credentials before proceeding.
  await page.getByRole("button", { name: /log out/i }).click();
  await expect(page).toHaveURL("/login");

  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /log in/i }).click();

  await expect(page).toHaveURL("/");

  await page.getByLabel(/video file/i).setInputFiles(VIDEO_PATH);
  await page.getByRole("button", { name: /upload/i }).click();

  await expect(page).toHaveURL(/\/attempts\/.+/);

  await expect(page.getByText(/status: completed|status: failed/i)).toBeVisible({
    timeout: 30_000,
  });

  await page.getByRole("button", { name: /delete this attempt/i }).click();
  await expect(page).toHaveURL("/");
});
