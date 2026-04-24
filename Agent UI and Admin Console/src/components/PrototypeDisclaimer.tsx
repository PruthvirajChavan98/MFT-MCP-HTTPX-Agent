import { useState, useEffect } from 'react'
import {
    AlertDialog,
    AlertDialogContent,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogAction,
} from './ui/alert-dialog'
import { ShieldAlert } from 'lucide-react'

const DISCLAIMER_ACCEPTED_KEY = 'mft_prototype_disclaimer_accepted_v1'
const DISCLAIMER_ACCEPTED_EVENT = 'mft:disclaimer-accepted'

export { DISCLAIMER_ACCEPTED_KEY, DISCLAIMER_ACCEPTED_EVENT }

export function PrototypeDisclaimer() {
    const [open, setOpen] = useState(false)

    useEffect(() => {
        if (!localStorage.getItem(DISCLAIMER_ACCEPTED_KEY)) {
            setOpen(true)
        }
    }, [])

    const handleAccept = () => {
        setOpen(false)
        try {
            window.localStorage.setItem(DISCLAIMER_ACCEPTED_KEY, 'true')
        } catch {
            // localStorage can be unavailable in restricted environments.
        }
        window.dispatchEvent(new CustomEvent(DISCLAIMER_ACCEPTED_EVENT))
    }

    return (
        <AlertDialog open={open} onOpenChange={setOpen}>
            <AlertDialogContent className="max-w-[480px] border-amber-200/50 bg-amber-50/95 backdrop-blur-xl shadow-2xl">
                <AlertDialogHeader className="space-y-4">
                    <div className="flex items-center gap-3 text-amber-700">
                        <div className="p-2.5 bg-amber-100 rounded-xl">
                            <ShieldAlert className="h-6 w-6" />
                        </div>
                        <AlertDialogTitle className="text-xl font-bold tracking-tight text-amber-900">
                            Prototype Disclaimer
                        </AlertDialogTitle>
                    </div>

                    <div className="space-y-3">
                        <AlertDialogDescription className="text-amber-900/80 text-[15px] font-medium leading-relaxed">
                            You are viewing a demonstration prototype.
                        </AlertDialogDescription>

                        <div className="p-4 bg-amber-100/50 rounded-xl border border-amber-200/50">
                            <p className="text-sm text-amber-800 leading-6">
                                <strong>Mock FinTech</strong> is a fictional entity. The services, products, and scenarios depicted in this application <span className="font-bold underline decoration-amber-500/50 decoration-2 underline-offset-2">do not exist in real life</span>.
                            </p>
                        </div>

                        <p className="text-xs text-amber-700/60 font-medium pt-1">
                            No real financial transactions or sensitive data processing will occur.
                        </p>
                    </div>
                </AlertDialogHeader>

                <AlertDialogFooter className="mt-2">
                    <AlertDialogAction
                        onClick={handleAccept}
                        className="w-full sm:w-auto bg-amber-600 hover:bg-amber-700 text-white shadow-lg shadow-amber-900/10 border-none transition-all hover:scale-[1.02] active:scale-[0.98] font-semibold"
                    >
                        I Understand, Proceed to Demo
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}
