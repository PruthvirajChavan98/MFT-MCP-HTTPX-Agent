import { RouterProvider } from 'react-router'
import { Toaster } from 'sonner'
import { router } from './routes'

import { PrototypeDisclaimer } from './components/PrototypeDisclaimer'

export default function App() {
  return (
    <>
      <PrototypeDisclaimer />
      <RouterProvider router={router} />
      <Toaster richColors position="top-right" />
    </>
  )
}
