import * as React from "react"
import * as MenubarPrimitive from "@radix-ui/react-menubar"
import { cn } from "./utils"
export const MenubarMenu = MenubarPrimitive.Menu
export const MenubarGroup = MenubarPrimitive.Group
export const MenubarPortal = MenubarPrimitive.Portal
export const MenubarSub = MenubarPrimitive.Sub
export const MenubarRadioGroup = MenubarPrimitive.RadioGroup
export const Menubar = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Root>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Root>>(({ className, ...props }, ref) => (<MenubarPrimitive.Root ref={ref} className={cn("flex h-10 items-center space-x-1 rounded-md border bg-background p-1", className)} {...props} />))
Menubar.displayName = MenubarPrimitive.Root.displayName
export const MenubarTrigger = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Trigger>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Trigger>>(({ className, ...props }, ref) => (<MenubarPrimitive.Trigger ref={ref} className={cn("flex cursor-default select-none items-center rounded-sm px-3 py-1.5 text-sm font-medium outline-none focus:bg-accent focus:text-accent-foreground data-[state=open]:bg-accent data-[state=open]:text-accent-foreground", className)} {...props} />))
MenubarTrigger.displayName = MenubarPrimitive.Trigger.displayName
export const MenubarContent = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Content>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Content>>(({ className, align = "start", alignOffset = -4, sideOffset = 8, ...props }, ref) => (<MenubarPrimitive.Portal><MenubarPrimitive.Content ref={ref} align={align} alignOffset={alignOffset} sideOffset={sideOffset} className={cn("z-50 min-w-[12rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md", className)} {...props} /></MenubarPrimitive.Portal>))
MenubarContent.displayName = MenubarPrimitive.Content.displayName
export const MenubarItem = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Item>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Item>>(({ className, ...props }, ref) => (<MenubarPrimitive.Item ref={ref} className={cn("relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent", className)} {...props} />))
MenubarItem.displayName = MenubarPrimitive.Item.displayName
export const MenubarSeparator = React.forwardRef<React.ElementRef<typeof MenubarPrimitive.Separator>, React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Separator>>(({ className, ...props }, ref) => (<MenubarPrimitive.Separator ref={ref} className={cn("-mx-1 my-1 h-px bg-muted", className)} {...props} />))
MenubarSeparator.displayName = MenubarPrimitive.Separator.displayName
export const MenubarShortcut = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => (<span className={cn("ml-auto text-xs tracking-widest text-muted-foreground", className)} {...props} />)
