import { Suspense } from 'react'
import { RouterProvider } from 'react-router'
import { ThemeProvider } from 'next-themes'
import { Toaster } from 'sonner'
import { router } from './routes'

import { PrototypeDisclaimer } from '@components/PrototypeDisclaimer'

export default function App() {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      storageKey="mft-admin-theme-v1"
      themes={['light', 'dark']}
    >
      <PrototypeDisclaimer />
      <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading...</div>}>
        <RouterProvider router={router} />
      </Suspense>
      <Toaster richColors position="top-right" theme="system" />
    </ThemeProvider>
  )
}
