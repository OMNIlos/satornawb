import type { SyntheticEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  SidebarSeparator,
} from '@/components/ui/sidebar'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { CURRENT_ROLE, visibleNavigationForRole, type NavItem } from '@/config/navigation'
import { cn } from '@/lib/utils'

function fallbackToRelativeBrandAsset(event: SyntheticEvent<HTMLImageElement>, fileName: string) {
  const image = event.currentTarget
  if (image.dataset.fallbackApplied === 'true') return
  image.dataset.fallbackApplied = 'true'
  image.src = `brand/${fileName}`
}

function isItemActive(item: NavItem, pathname: string): boolean {
  if (item.path === pathname) return true
  if (item.children?.some((c) => c.path === pathname)) return true
  if (item.path !== '/' && pathname.startsWith(item.path + '/')) return true
  return false
}

const activeAccent =
  'data-[active=true]:bg-white/10 data-[active=true]:text-white data-[active=true]:font-medium ' +
  'relative hover:translate-x-px hover:bg-white/[0.06] hover:text-white/85'

const activeAccentSub =
  'data-[active=true]:bg-white/[0.12] data-[active=true]:text-white/95 data-[active=true]:font-medium hover:bg-white/10 hover:text-white'

function NavItemButton({ item, pathname }: { item: NavItem; pathname: string }) {
  const active = isItemActive(item, pathname)
  const exact = item.path === pathname
  const isSoon = item.badge === 'soon'
  const Icon = item.icon

  if (item.children && item.children.length > 0) {
    return (
      <Collapsible defaultOpen={active} className="group/collapsible">
        <SidebarMenuItem>
          <CollapsibleTrigger asChild>
            <SidebarMenuButton
              isActive={exact}
              tooltip={item.label}
              className={cn('mx-1.5 my-0.5 h-[38px] rounded-lg px-3 text-sm font-normal transition-[background,color,transform]', activeAccent)}
            >
              {Icon && <Icon className="size-4" />}
              <span className="truncate">{item.label}</span>
              <ChevronRight className="ml-auto size-4 shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
            </SidebarMenuButton>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <SidebarMenuSub className="mx-3 mb-3 mt-1 rounded-lg border-0 bg-white/[0.045] px-1.5 py-2 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.035)]">
              {item.children.map((child) => {
                const childSoon = child.badge === 'soon'
                const childActive = child.path === pathname
                return (
                  <SidebarMenuSubItem key={child.id}>
                    <SidebarMenuSubButton
                      asChild
                      isActive={childActive}
                      className={cn('h-[30px] rounded-md px-2.5 text-[13px] transition-[background,color,transform]', activeAccentSub)}
                    >
                      <Link
                        to={child.path}
                        title={child.label}
                        aria-current={childActive ? 'page' : undefined}
                        aria-disabled={childSoon || undefined}
                      >
                        {child.icon && <child.icon className="size-3.5 shrink-0 text-muted-foreground/70" />}
                        <span className="truncate">{child.label}</span>
                        {childSoon && (
                          <span className="ml-auto shrink-0 text-[10px] uppercase tracking-wider text-sidebar-foreground/55">
                            Скоро
                          </span>
                        )}
                      </Link>
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                )
              })}
            </SidebarMenuSub>
          </CollapsibleContent>
        </SidebarMenuItem>
      </Collapsible>
    )
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={active}
        tooltip={item.label}
        className={cn('mx-1.5 my-0.5 h-[38px] rounded-lg px-3 text-sm font-normal transition-[background,color,transform]', activeAccent)}
      >
        <Link
          to={item.path}
          title={item.label}
          aria-current={exact ? 'page' : undefined}
          aria-disabled={isSoon || undefined}
        >
          {Icon && <Icon className="size-4 shrink-0" />}
          <span className="truncate">{item.label}</span>
        </Link>
      </SidebarMenuButton>
      {isSoon && (
        <SidebarMenuBadge className="text-[10px] uppercase tracking-wider text-sidebar-foreground/55">
          Скоро
        </SidebarMenuBadge>
      )}
    </SidebarMenuItem>
  )
}

export function AppSidebar() {
  const { pathname } = useLocation()
  const navigation = visibleNavigationForRole(CURRENT_ROLE)

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="mb-2 min-h-[54px] border-b border-white/[0.06] px-[14px] pb-3 pt-[14px]">
        <div className="flex items-center gap-2 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <img
            src="/brand/satorna-logo-white.svg"
            alt="Satorna"
            onError={(event) => fallbackToRelativeBrandAsset(event, 'satorna-logo-white.svg')}
            className="h-auto w-[136px] opacity-90 group-data-[collapsible=icon]:hidden"
          />
          <img
            src="/brand/satorna-icon.svg"
            alt="Satorna"
            onError={(event) => fallbackToRelativeBrandAsset(event, 'satorna-icon.svg')}
            className="hidden size-7 rounded-lg bg-white/95 p-1 shadow-sm group-data-[collapsible=icon]:block"
          />
        </div>
      </SidebarHeader>

      <SidebarContent className="gap-0 overflow-y-auto overflow-x-visible pb-[22px]">
        {navigation.map((group, idx) => (
          <SidebarGroup key={group.id} className="p-0">
            {idx > 0 && (
              <SidebarSeparator className="mx-0 mb-1 group-data-[collapsible=icon]:block hidden" />
            )}
            {group.label && <SidebarGroupLabel className="h-auto px-[14px] pb-1 pt-3 text-[10.5px] font-semibold uppercase tracking-[0.09em] text-sidebar-foreground/35">{group.label}</SidebarGroupLabel>}
            <SidebarGroupContent>
              <SidebarMenu className="gap-0">
                {group.items.map((item) => (
                  <NavItemButton key={item.id} item={item} pathname={pathname} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter />

      <SidebarRail />
    </Sidebar>
  )
}
