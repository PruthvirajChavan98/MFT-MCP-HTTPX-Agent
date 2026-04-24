import { test, expect } from '@playwright/test'

/**
 * Baseline visual regression for the admin login page.
 *
 * This is the first spec under Playwright because the route is public (no auth
 * gate) — it proves the visual-regression pipeline works end-to-end before we
 * invest in an auth-storage-state story for the gated `/admin/*` pages.
 *
 * Font-loading is the one source of legitimate pixel drift; we wait for
 * `document.fonts.ready` before snapshotting. If that proves insufficient on
 * CI, bump `toHaveScreenshot({ maxDiffPixelRatio })` on a per-test basis
 * rather than lowering the project-level threshold.
 */
test.describe('LoginPage visual', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/admin/login')
    // Wait for IBM Plex Sans + JetBrains Mono to be loaded before screenshot,
    // otherwise Chrome renders a fallback for ~30 ms and the diff fails.
    await page.evaluate(() => document.fonts.ready)
    // Stop the pulsing animation on the "press ⏎" hint — purely cosmetic but
    // would fail an otherwise identical snapshot.
    await page.addStyleTag({
      content: `*, *::before, *::after { animation: none !important; transition: none !important; }`,
    })
  })

  test('renders the dark-default login card', async ({ page }) => {
    await expect(page).toHaveScreenshot('login-dark.png', {
      fullPage: true,
    })
  })

  test('the product mark is present above the card', async ({ page }) => {
    await expect(page.getByText('MFT Admin')).toBeVisible()
    await expect(page.getByText('production console')).toBeVisible()
  })

  test('the form has email + password fields + submit button', async ({ page }) => {
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible()
  })
})
