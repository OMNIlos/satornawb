import { Outlet } from 'react-router-dom'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AppSidebar } from './AppSidebar'
import { AppHeader } from './AppHeader'
import { CommandPalette } from '@/components/CommandPalette'
import { useCommandPalette } from '@/hooks/useCommandPalette'
import { NotificationProvider } from '@/features/notifications/NotificationProvider'

export function AppShell() {
  const { open, setOpen } = useCommandPalette()

  return (
    <TooltipProvider delayDuration={150}>
      <SidebarProvider>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded focus:text-sm focus:font-medium"
        >
          Перейти к содержимому
        </a>
        <AppSidebar />
        <NotificationProvider>
          <SidebarInset>
            <AppHeader />
            <main id="main-content" className="flex-1 overflow-auto">
              <Outlet />
            </main>
          </SidebarInset>
        </NotificationProvider>
        <CommandPalette open={open} onOpenChange={setOpen} />
      </SidebarProvider>
    </TooltipProvider>
  )
}
