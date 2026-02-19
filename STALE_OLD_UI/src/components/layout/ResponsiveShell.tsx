import { Component, JSX } from 'solid-js';
import { useViewport } from '../../hooks/useViewport';
import clsx from 'clsx';

interface ResponsiveShellProps {
  children: JSX.Element;
  className?: string;
}

/**
 * ResponsiveShell
 * * The root layout container that:
 * 1. Adapts to '--app-height' (Visual Viewport).
 * 2. Centers content on Ultrawide monitors.
 * 3. Prevents "rubber-band" scrolling on body.
 */
const ResponsiveShell: Component<ResponsiveShellProps> = (props) => {
  // Initialize the viewport listener
  useViewport();

  return (
    <div
      class={clsx(
        "relative w-full overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100",
        props.className
      )}
      style={{
        height: 'var(--app-height, 100vh)', // Fallback to 100vh if JS fails
        'overscroll-behavior': 'none',       // Stop pull-to-refresh
      }}
    >
      {/* Ultrawide Centering Container
        - On mobile: 100% width
        - On Ultrawide: Max 1920px, centered, with subtle borders
      */}
      <div class="mx-auto flex h-full w-full max-w-480 flex-col shadow-2xl ultrawide:border-x ultrawide:border-slate-800">
        {props.children}
      </div>
    </div>
  );
};

export default ResponsiveShell;
