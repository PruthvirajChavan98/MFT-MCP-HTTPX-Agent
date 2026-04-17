import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const CSS_PATH = resolve(__dirname, './chat-widget.css')

/**
 * Regression guard for the chat widget's theme-scope bug.
 *
 * Background:
 *   When the admin ThemeProvider applies `.dark` to <html>, every descendant
 *   CSS custom property resolves in dark-mode scope. The chat widget renders
 *   on a white card but used to bind `--tf-chat-foreground` → `var(--foreground)`,
 *   which resolved to `#f5f5f4` under `.dark`. List items inherited that
 *   value and became invisible on white.
 *
 *   Fix: the widget's `--tf-chat-*` custom properties are now hardcoded to
 *   light-mode literal values, and list items carry an explicit `color`
 *   declaration so they never fall back to the outer theme.
 *
 *   If a future change re-binds these tokens to `var(--foreground)` et al.
 *   or drops the explicit `color` on `<li>`, this test fails and re-opens
 *   the regression.
 */
describe('chat-widget.css theme-scope invariant', () => {
  const css = readFileSync(CSS_PATH, 'utf-8')

  it('does NOT bind the chat-widget tokens to the global theme vars', () => {
    // Strip comments so we don't match var(--foreground) references inside
    // the explanatory comment at the top of the file.
    const codeOnly = css.replace(/\/\*[\s\S]*?\*\//g, '')

    expect(codeOnly).not.toMatch(/--tf-chat-foreground:\s*var\(--foreground\)/)
    expect(codeOnly).not.toMatch(/--tf-chat-muted-foreground:\s*var\(--muted-foreground\)/)
    expect(codeOnly).not.toMatch(/--tf-chat-background:\s*var\(--background\)/)
    expect(codeOnly).not.toMatch(/--tf-chat-border:\s*var\(--border\)/)
    expect(codeOnly).not.toMatch(/--tf-chat-muted:\s*var\(--muted\)/)
    expect(codeOnly).not.toMatch(/--tf-chat-primary:\s*var\(--primary\)/)
  })

  it('locks the widget to light-mode literal color values', () => {
    // Hardcoded hex values are stable; the specific shade is intentional so
    // the widget reads correctly on the white assistant card regardless of
    // any ancestor theme class.
    expect(css).toMatch(/--tf-chat-foreground:\s*#0a0a0a/)
    expect(css).toMatch(/--tf-chat-bg:\s*#ffffff/)
  })

  it('carries an explicit color declaration on list items', () => {
    // Without this, <li> inherits from the outer theme scope and the very
    // bug this test guards against would re-appear.
    expect(css).toMatch(/\.tf-chat-streamdown li\s*\{[^}]*color:\s*var\(--tf-chat-foreground\)/)
    expect(css).toMatch(/\.tf-chat-streamdown ul,\s*\n?\s*\.tf-chat-streamdown ol\s*\{[^}]*color:\s*var\(--tf-chat-foreground\)/)
  })
})
