# DEFECTS — SaaS «Огни» Shell — 2026-04-24

**QA Agent**: EvidenceQA
**Evidence Date**: 24 апреля 2026
**Target**: http://localhost:5175 — shell (AppShell + AppSidebar + AppHeader + CommandPalette + ThemeToggle + ComingSoon + navigation.ts + index.css)
**Viewport coverage**: 1440×900 (desktop), 375×812 (mobile)
**Themes tested**: light, dark
**Screenshots**: `frontend/defects/*.png`

---

## Сводная таблица

| # | Severity | Defect | Evidence | File:Line |
|---|---|---|---|---|
| 1 | **BLOCKER** | `CommandDialog` без `DialogTitle` — Radix a11y-ошибка в консоли при каждом открытии ⌘K | `11-cmdk-dark.png` + console log | `src/components/CommandPalette.tsx:26` |
| 2 | **HIGH** | Колонка **P_MIN** переносит «1 508,34 ₽» на 2 строки во всех крупных значениях (84px контента в 72px area) | `01-light-repricer-landing.png`, `09-dark-table.png`, `13-light-table-final.png` | `src/pages/WBRepricer*.tsx` (table cell `<td className="px-3 py-2.5 text-right">`) |
| 3 | **HIGH** | Sidebar sub-item **«Сводный дайджест»** обрезан (`scrollWidth=132 > clientWidth=129`), нет `title` для тултипа | `15-reports-expanded.png` | `src/layouts/AppSidebar.tsx:63` (`<span className="truncate">`) |
| 4 | **HIGH** | Breadcrumbs на SKU-детали теряют префикс группы «WB» — на списке «WB / Репрайсер», на SKU «Репрайсер / FBBT_55» | `12-sku-breadcrumb.png` | `src/layouts/AppHeader.tsx:31-42` (ветка `pathname.startsWith(item.path + '/')` не пушит `group.label`) |
| 5 | **HIGH** | Активный пункт навигации не имеет `aria-current="page"` — ридеры не понимают текущую страницу | `browser_evaluate` показал `aria_current: null` | `src/layouts/AppSidebar.tsx:82` (`SidebarMenuButton` не прокидывает `aria-current`) |
| 6 | **MEDIUM** | Sidebar hover ≈ active state — визуально неотличимы (оба `bg-sidebar-accent`). На скрине «Чаты» с ховером на «Отзывы WB» неясно, где я нахожусь | `08-dark-desktop.png`, `13-light-table-final.png` | `src/components/ui/sidebar.tsx` (classes для `data-active=true` и `:hover` обе выставляют `bg-sidebar-accent`) |
| 7 | **MEDIUM** | WCAG AA contrast fails: `Shell · v0.3` (10px, **4.10:1**) и «Скоро» badge (10px, **4.23:1**) в dark — оба < 4.5:1 | `08-dark-desktop.png`, вычисления WCAG | `src/layouts/AppSidebar.tsx:36,126` (`text-muted-foreground/70`) |
| 8 | **MEDIUM** | Disabled-по-смыслу пункты `badge:'soon'` остаются кликабельными, фокусируются Tab'ом, без `aria-disabled`. Ведут на stub-страницу | `browser_evaluate`: `disabled:false, tabindex:null, pointerEvents:auto` | `src/layouts/AppSidebar.tsx:82-90` (нет `aria-disabled`/`tabIndex=-1` когда `badge==='soon'`) |
| 9 | **MEDIUM** | Focus ring на sidebar пунктах заполняет всю ширину (239px), грубо визуально. Остаётся видимым после route change | `14-pmin-wrap-detail.png` (виден большой ring вокруг «Дашборд») | `src/components/ui/sidebar.tsx` (`focus-visible:ring-2` на `peer/menu-button flex w-full`) |
| 10 | **MEDIUM** | «ещё 18ч» / «ещё 3ч» под карантин-пиллами — красный текст `rgb(239,68,68)` на розовом overlay, contrast **4.82:1** (borderline AA, fail AAA) | `09-dark-table.png` (строки HCBT_07, FBBT_31) | `src/pages/WBRepricer*.tsx` (колонка «Статус» секундария) |
| 11 | **LOW** | В свёрнутом сайдбаре (collapsible=icon) теряются **section labels** «WB / АВИТО / ПРОИЗВОДСТВО / СИСТЕМА» — иконки идут сплошняком без разделения | `10-sidebar-collapsed.png` | `src/components/ui/sidebar.tsx` — `SidebarGroupLabel` скрывается через `group-data-[collapsible=icon]:hidden` без визуального разделителя |
| 12 | **LOW** | Active state в свёрнутом сайдбаре слабо заметен — `rgb(29,40,58)` на `rgb(11,16,30)` сайдбар-bg даёт контраст ~1.6:1 (фон-к-фону) | `10-sidebar-collapsed.png` — иконку Tag у «Репрайсер» почти не видно как активную | `src/index.css:82` (sidebar-accent слишком близок к sidebar-background в dark) |
| 13 | **LOW** | CommandPalette: child items рендерятся без иконок (parent items с иконками) — неровный визуальный ритм | `11-cmdk-dark.png` (строка «Отчёты / Продажи» без иконки) | `src/components/CommandPalette.tsx:51-54` |
| 14 | **LOW** | Мобильный viewport 375px: карантин-подсветка строки доминирует, но колонки статуса/цены/корзин скрыты — красный цвет без контекста не информативен | `07-mobile-375.png` | `src/pages/WBRepricer*.tsx` (table-responsive logic) |

---

## Визуальная детализация с доказательствами

### 1. BLOCKER — CommandDialog без DialogTitle

**Evidence**: `defects/11-cmdk-dark.png` + консольная ошибка (зафиксирована `browser_console_messages`):
```
[ERROR] `DialogContent` requires a `DialogTitle` for the component to be accessible for screen reader users.
If you want to hide the `DialogTitle`, you can wrap it with our VisuallyHidden component.
```
Повторяется при **каждом** открытии ⌘K.

**Fix** (`src/components/CommandPalette.tsx`):
```tsx
import { VisuallyHidden } from '@radix-ui/react-visually-hidden'
import { DialogTitle, DialogDescription } from '@/components/ui/dialog'

<CommandDialog open={open} onOpenChange={onOpenChange}>
  <VisuallyHidden><DialogTitle>Поиск по приложению</DialogTitle></VisuallyHidden>
  <VisuallyHidden><DialogDescription>Переход между разделами</DialogDescription></VisuallyHidden>
  <CommandInput placeholder="Поиск по модулям и разделам…" />
  …
```

---

### 2. HIGH — P_MIN колонка режет «1 508,34 ₽»

**Evidence**: `defects/01-light-repricer-landing.png` — виден двустрочный P_MIN в строках HCBT_07, HBBT_22, HCBT_19, LBBT_11, HBBT_07, LCBT_08.

**Root cause** (подтверждено `browser_evaluate`):
- `<td class="px-3 py-2.5 text-right">` → ширина **96px**, контент-area после padding = **72px**
- `<span class="text-sm font-mono text-muted-foreground">1&nbsp;508,34 ₽</span>` — только между «1» и «508» стоит `&nbsp;` (0xA0), между «34» и «₽» обычный пробел (0x20)
- `nowrap` width = **84px** > **72px** content area → wraps into 2 lines

**Fix**: либо `whitespace-nowrap` на span/td, либо неразрывный пробел перед `₽`:
```tsx
// replace all formatPrice("1 508,34 ₽") → "1 508,34 ₽"
// OR add whitespace-nowrap class to the span:
<span className="text-sm font-mono text-muted-foreground whitespace-nowrap">
```
Рекомендую оба (`&nbsp;` + `whitespace-nowrap`) + расширить колонку до 7rem (`w-28`).

---

### 3. HIGH — «Сводный дайджест» обрезан многоточием

**Evidence**: `defects/15-reports-expanded.png` — видно «Сводный дайдж...», также «Неделя-к-неделе» на границе.

**Measurements**: `scrollWidth=132, clientWidth=129, truncated:true, title:null`.

**Fix** (`src/layouts/AppSidebar.tsx:62-69`):
```tsx
<Link to={child.path}>
  <span className="truncate" title={child.label}>{child.label}</span>
  {child.badge === 'soon' && (…)}
</Link>
```
Либо сократить label «Сводный дайджест» → «Дайджест» в `navigation.ts:77`. Либо шире sub-menu (удалить `pl-` у `SidebarMenuSub`).

---

### 4. HIGH — Breadcrumbs на /sku/* без группы

**Evidence**: `defects/12-sku-breadcrumb.png` — показывает «Репрайсер / FBBT_55», нет префикса «WB».

**Для сравнения** на `/wb/repricer` breadcrumb = «WB / Репрайсер» (correct) — см. `04-fresh-light.png`.

**Fix** (`src/layouts/AppHeader.tsx`, строка 31):
```tsx
for (const g of NAVIGATION) {
  for (const item of g.items) {
    if (item.path !== '/' && pathname.startsWith(item.path + '/')) {
      if (g.label) crumbs.unshift({ label: g.label })  // ← ДОБАВИТЬ ЭТО
      crumbs.push({ label: item.label, path: item.path })
      …
```
Или вынести в начало функции: `if (group?.label) crumbs.push({label: group.label})` ДО цикла детали.

---

### 5. HIGH — Active nav link без aria-current

**Evidence** (`browser_evaluate`): активная ссылка `data-active="true"`, но `aria-current: null`.

**Fix** (`src/layouts/AppSidebar.tsx:82`):
```tsx
<SidebarMenuButton asChild isActive={active} tooltip={item.label}>
  <Link to={item.path} aria-current={active ? 'page' : undefined}>
    {Icon && <Icon className="size-4" />}
    <span>{item.label}</span>
  </Link>
</SidebarMenuButton>
```
То же для `<Link>` в `SidebarMenuSubButton` (строки 62, 83).

---

### 6. MEDIUM — Hover vs Active неотличимы

**Evidence**: `defects/08-dark-desktop.png` (Чаты-страница с hover на «Отзывы WB» — смотрится как активный). `defects/13-light-table-final.png` — то же.

**Root cause**: `data-active="true"` и `:hover` обе применяют `bg-sidebar-accent`. Отличается только `font-medium`.

**Fix**: добавить явный маркер активного — левая вертикальная полоска цвета primary + жирнее bg:
```tsx
// в sidebarMenuButtonVariants (components/ui/sidebar.tsx):
// active:  "data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium data-[active=true]:border-l-2 data-[active=true]:border-sidebar-primary"
// hover:   "hover:bg-sidebar-accent/60"  ← 60% прозрачности вместо 100%
```

---

### 7. MEDIUM — WCAG AA contrast fails

**Evidence** (WCAG calc в browser_evaluate):
- `Shell · v0.3` (fontSize: 10px, color: `rgba(148,163,184,0.7)`) на sidebar-bg `rgb(11,16,30)` = **4.10:1** — FAIL (требуется ≥4.5:1 для текста <18px)
- `Скоро` badge (fontSize: 10px, тот же цвет) на body-bg `rgb(8,12,22)` = **4.23:1** — FAIL

**Fix** (`src/layouts/AppSidebar.tsx:36,126`):
```tsx
// было:  text-muted-foreground/70
// стало: text-muted-foreground  (без /70 — 7.62:1 PASS)
// ИЛИ: увеличить fontSize до 11-12px и /80
```

---

### 8. MEDIUM — «Скоро» пункты кликабельны + фокусируются

**Evidence** (`browser_evaluate`):
```json
{"href":"/dashboard","disabled":false,"tabindex":null,"pointerEvents":"auto"}
```
Tab по сайдбару фокусирует «Дашборд» (первый Скоро-пункт), Enter → навигация на stub.

**Fix** (`src/layouts/AppSidebar.tsx:80-90`):
```tsx
const isSoon = item.badge === 'soon'
return (
  <SidebarMenuItem>
    <SidebarMenuButton
      asChild={!isSoon}
      isActive={active}
      tooltip={item.label}
      aria-disabled={isSoon || undefined}
      tabIndex={isSoon ? -1 : undefined}
      className={isSoon ? 'opacity-60 cursor-default' : undefined}
    >
      {isSoon ? (
        <div>{Icon && <Icon className="size-4" />}<span>{item.label}</span></div>
      ) : (
        <Link to={item.path} aria-current={active ? 'page' : undefined}>
          {Icon && <Icon className="size-4" />}
          <span>{item.label}</span>
        </Link>
      )}
    </SidebarMenuButton>
    {isSoon && <SoonBadge />}
  </SidebarMenuItem>
)
```

---

### 9. MEDIUM — Массивный focus ring на sidebar

**Evidence**: `defects/14-pmin-wrap-detail.png` — «Дашборд» обёрнут рамкой на всю ширину 239px.

**Fix**: заменить `focus-visible:ring-2 ring-sidebar-ring` на inset-rounded outline:
```tsx
// components/ui/sidebar.tsx sidebarMenuButtonVariants:
// "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-offset-0"
// заменить на inset: "focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-sidebar-primary"
```

---

### 10. MEDIUM — «ещё 18ч» red-on-red contrast

**Evidence**: `defects/09-dark-table.png`. WCAG calc = **4.82:1** (AA PASS для large, borderline для 14px).

**Fix**: использовать `--destructive-foreground` или `text-red-300` на тёмном:
```tsx
// WBRepricer*.tsx (строки карантин):
// было:  <span className="text-xs text-red-500">ещё 18ч</span>
// стало: <span className="text-xs text-red-400">ещё 18ч</span>  // 5.5:1 на 10%-overlay
```

---

### 11. LOW — Collapsed sidebar теряет section разделители

**Evidence**: `defects/10-sidebar-collapsed.png` — иконки WB/АВИТО/ПРОИЗВОДСТВО/СИСТЕМА идут сплошным потоком 19 штук. Mental grouping потерян.

**Fix**: добавить `<Separator />` между группами в collapsed mode:
```tsx
// AppSidebar.tsx вокруг SidebarGroup:
<SidebarGroup key={group.id}>
  {group.label ? (
    <>
      <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
      {/* visible только в collapsed */}
      <hr className="mx-2 my-1 border-sidebar-border hidden group-data-[collapsible=icon]:block" />
    </>
  ) : null}
  …
```

---

### 12. LOW — Active state в collapsed почти не виден

**Evidence**: `defects/10-sidebar-collapsed.png` — квадратик под Tag-иконкой едва заметен. Тёмный на тёмном.

**Fix** (`src/index.css:82`):
```css
.dark {
  --sidebar-accent: 217 33% 25%;   /* было 17% — увеличить lightness */
}
```
Или добавить обводку для active в collapsed: `data-[active=true]:ring-1 data-[active=true]:ring-sidebar-primary/50`.

---

### 13. LOW — Child items в CommandPalette без иконок

**Evidence**: `defects/11-cmdk-dark.png` — «Отчёты / Продажи» только текст, parent «Отчёты» с иконкой.

**Fix** (`src/components/CommandPalette.tsx:45-55`):
```tsx
<CommandItem key={child.id} value={…} onSelect={() => go(child.path)}>
  {item.icon && <item.icon className="size-4 opacity-50" />}  {/* наследуем иконку родителя */}
  <span className="text-muted-foreground">
    {item.label} <span className="text-muted-foreground/50">/</span> {child.label}
  </span>
</CommandItem>
```

---

### 14. LOW — Мобильный viewport: карантин-подсветка без контекста

**Evidence**: `defects/07-mobile-375.png` — видны только ID артикула и название; карантин строки горят красным, но WHY? (нет статуса, нет срока, нет цены). Красный → алерт → но информации ноль.

**Fix**: либо показывать компактный badge статуса справа, либо убирать row-level highlight на <768px (делать только иконкой слева):
```tsx
// WBRepricer*.tsx:
// className={`${isCarantine ? (isMobile ? '' : 'bg-red-500/10') : ''}`}
```

---

## 🎯 Итоговая честная оценка

**Realistic Rating**: **B-** (ни в коем случае не A+)
**Design Level**: **Good** (не Excellent) — fundamentals есть, но много мелких и 1 BLOCKER a11y-ошибка
**Production Readiness**: **NEEDS WORK** — 1 blocker, 4 high, 5 medium, 4 low = **14 дефектов до зелёного света**

**Приоритет фиксов**:
1. BLOCKER #1 (1 час)
2. HIGH #2, #3, #4, #5 (4–6 часов суммарно)
3. MEDIUM #6, #7, #8, #9, #10 (4–8 часов)
4. LOW #11, #12, #13, #14 (можно в следующем спринте)

**Timeline**: ~2 дня работы на одного фронтендера до повторного QA.
**Re-test Required**: YES после внесения правок.

---

**QA Agent**: EvidenceQA
**Screenshots directory**: `/Users/dima/Downloads/Projects/SAAS для Огней/frontend/defects/`
**Evidence files**: 01-light-repricer-landing.png → 15-reports-expanded.png (15 скриншотов)
