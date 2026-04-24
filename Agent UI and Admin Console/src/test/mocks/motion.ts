/**
 * Shared mock factory for `motion/react`.
 *
 * Usage in test files:
 *   import { motionReactMock } from '@/test/mocks/motion'
 *   vi.mock('motion/react', motionReactMock)
 */
import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import { createElement, forwardRef } from 'react'

const cache = new Map<string, ReturnType<typeof forwardRef>>()

function createMotionElement(tag: string) {
  if (cache.has(tag)) return cache.get(tag)!

  const component = forwardRef<
    HTMLElement,
    ComponentPropsWithoutRef<'div'> & { children?: ReactNode }
  >(({ children, ...props }, ref) => {
    const {
      animate,
      exit,
      initial,
      layout,
      transition,
      viewport,
      whileHover,
      whileInView,
      whileTap,
      ...domProps
    } = props as Record<string, unknown>

    void animate
    void exit
    void initial
    void layout
    void transition
    void viewport
    void whileHover
    void whileInView
    void whileTap

    return createElement(tag, { ...domProps, ref }, children)
  })

  cache.set(tag, component)
  return component
}

const motionProxy = new Proxy(
  {},
  { get: (_: unknown, tag: string) => createMotionElement(tag) },
)

/**
 * Pass as the second argument to `vi.mock('motion/react', motionReactMock)`.
 *
 * Returns `motion` proxy and common no-op exports (`AnimatePresence`, `useInView`).
 * Tests can spread additional overrides after importing.
 */
export function motionReactMock() {
  return {
    motion: motionProxy,
    AnimatePresence: ({ children }: { children?: ReactNode }) => children,
    useInView: () => true,
  }
}
