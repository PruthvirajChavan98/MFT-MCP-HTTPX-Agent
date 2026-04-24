import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config — visual regression + future e2e coverage.
 *
 * Baseline screenshots live at `tests/visual/<spec>.spec.ts-snapshots/*` and
 * are authoritative for the commit SHA they were generated on. Regenerate via
 * `npm run test:visual:update` after an intentional UI change.
 *
 * Deliberate scope:
 *   - Vitest stays the default `npm run test`
 *   - Playwright is opt-in via `npm run test:visual`
 *   - `webServer` boots `npm run dev` (vite) on first run
 *   - Single browser (chromium) — multi-browser coverage is a later concern
 */
export default defineConfig({
  testDir: './tests/visual',
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html', { open: 'never' }], ['list']],
  use: {
    baseURL: process.env.PW_BASE_URL ?? 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    colorScheme: 'dark',
  },
  expect: {
    // Visual diffs must be bit-perfect by default. Adjust per-test via
    // `toHaveScreenshot({ maxDiffPixels: N })` where fonts or fractional
    // rendering can legitimately drift.
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      animations: 'disabled',
    },
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'chromium-mobile',
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: process.env.PW_BASE_URL
    ? undefined
    : {
        command: 'npm run dev',
        url: 'http://127.0.0.1:5173',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
})
