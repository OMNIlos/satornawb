import { useNavigate } from 'react-router-dom'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { CURRENT_ROLE, visibleNavigationForRole } from '@/config/navigation'

type CommandPaletteProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate()
  const navigation = visibleNavigationForRole(CURRENT_ROLE)

  function go(path: string) {
    onOpenChange(false)
    navigate(path)
  }

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Поиск по модулям и разделам…" />
      <CommandList>
        <CommandEmpty>Ничего не найдено</CommandEmpty>
        {navigation.map((group) => (
          <CommandGroup key={group.id} heading={group.label ?? 'Общее'}>
            {group.items.flatMap((item) => {
              const entries = [
                <CommandItem
                  key={item.id}
                  value={`${item.label} ${item.id}`}
                  onSelect={() => go(item.path)}
                >
                  {item.icon && <item.icon className="size-4" />}
                  <span>{item.label}</span>
                </CommandItem>,
              ]
              if (item.children) {
                for (const child of item.children) {
                  entries.push(
                    <CommandItem
                      key={child.id}
                      value={`${item.label} / ${child.label} ${child.id}`}
                      onSelect={() => go(child.path)}
                    >
                      <span className="pl-6 text-muted-foreground">
                        {item.label} / {child.label}
                      </span>
                    </CommandItem>,
                  )
                }
              }
              return entries
            })}
          </CommandGroup>
        ))}
      </CommandList>
    </CommandDialog>
  )
}
