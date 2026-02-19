export function SidebarProvider({ children }: { children: React.ReactNode }) { return <>{children}</> }
export function Sidebar({ children, className }: { children?: React.ReactNode; className?: string }) { return <aside className={className}>{children}</aside> }
export function SidebarContent({ children }: { children?: React.ReactNode }) { return <div>{children}</div> }
export function SidebarMenu({ children }: { children?: React.ReactNode }) { return <ul>{children}</ul> }
export function SidebarMenuItem({ children }: { children?: React.ReactNode }) { return <li>{children}</li> }
export function SidebarMenuButton({ children, asChild, isActive, className }: { children?: React.ReactNode; asChild?: boolean; isActive?: boolean; className?: string }) { return <button className={className}>{children}</button> }
