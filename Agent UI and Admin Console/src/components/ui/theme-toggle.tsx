import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'

/**
 * Theme toggle — flips between `light` and `dark` via next-themes.
 * Renders a stable placeholder on first paint to avoid hydration-flash
 * swapping the icon on mount.
 *
 * Visual intent: part of the "Terminal-grade Fintech" header identity —
 * no decorative frame, a single-icon control with a hairline on hover.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // next-themes resolves the actual theme client-side; avoid flashing the
  // wrong icon on the first paint by rendering a placeholder until mount.
  useEffect(() => {
    setMounted(true)
  }, [])

  const isDark = mounted && resolvedTheme === 'dark'

  return (
    <button
      type="button"
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className="inline-flex size-8 items-center justify-center rounded-md border border-transparent text-muted-foreground transition-colors hover:border-border hover:bg-accent hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {mounted ? (
        isDark ? (
          <Moon className="size-4" />
        ) : (
          <Sun className="size-4" />
        )
      ) : (
        // Placeholder keeps layout stable pre-mount
        <span className="size-4" aria-hidden />
      )}
    </button>
  )
}
