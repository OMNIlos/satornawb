### Task 5: Frontend Stale and Source Cache Miss UX

**Files:**
- Modify: `D:\ogni-frontend\frontend\src\features\vella-parity\VellaHtmlParityPage.tsx`
- Test: `D:\ogni-frontend\frontend\src\features\vella-parity\reportSourceCacheMiss.test.ts`

**Interfaces:**
- Consumes: backend `cache.status = "source_cache_miss"` and `cache.missingSources`.
- Produces: `reportHasSourceCacheMiss(report: unknown) -> boolean`.
- Produces: `reportSourceCacheMissMessage(report: unknown) -> string`.

- [ ] **Step 1: Write frontend unit tests**

Create `D:\ogni-frontend\frontend\src\features\vella-parity\reportSourceCacheMiss.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { reportHasSourceCacheMiss, reportSourceCacheMissMessage } from './VellaHtmlParityPage'

describe('report source cache miss helpers', () => {
  it('detects source cache miss reports', () => {
    const report = {
      cache: {
        status: 'source_cache_miss',
        missingSources: ['finance', 'ads'],
      },
    }

    expect(reportHasSourceCacheMiss(report)).toBe(true)
    expect(reportSourceCacheMissMessage(report)).toContain('finance, ads')
  })

  it('ignores ordinary report cache misses', () => {
    expect(reportHasSourceCacheMiss({ cache: { status: 'missing' } })).toBe(false)
    expect(reportSourceCacheMissMessage({ cache: { status: 'missing' } })).toBe('Данные отчёта собираются')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `D:\ogni-frontend\frontend`: `npm test -- --run src/features/vella-parity/reportSourceCacheMiss.test.ts`

Expected: FAIL because helpers are not exported.

- [ ] **Step 3: Export cache miss helpers**

In `VellaHtmlParityPage.tsx`, add near `backgroundReportIsRefreshing`:

```typescript
export function reportHasSourceCacheMiss(report: unknown) {
  const cache = (report as { cache?: { status?: string } } | null)?.cache
  return cache?.status === 'source_cache_miss'
}

export function reportSourceCacheMissMessage(report: unknown) {
  const cache = (report as { cache?: { missingSources?: unknown } } | null)?.cache
  if (!reportHasSourceCacheMiss(report)) return 'Данные отчёта собираются'
  const missing = Array.isArray(cache?.missingSources)
    ? cache.missingSources.map(String).filter(Boolean)
    : []
  return missing.length
    ? `Нет source cache для: ${missing.join(', ')}. Запустите WB sync или дождитесь расписания.`
    : 'Нет source cache для выбранного периода. Запустите WB sync или дождитесь расписания.'
}
```

- [ ] **Step 4: Preserve ready state while refreshing or missing**

In each report island loader that currently does `setState({ status: 'loading' })` before fetching, replace that line with:

```typescript
setState(retainReadyReportWhileRefreshing)
```

In each report island branch that receives a report with source cache miss and no rows, set ready state with the report instead of error:

```typescript
if (reportHasSourceCacheMiss(report)) {
  setState({ status: 'ready', report: report ?? {} })
  return
}
```

Apply this to RNP, P&L, expenses, ads, stock, and week-over-week loaders.

- [ ] **Step 5: Show source cache miss message in source strips**

Where report source strip cards currently show loading text for ready reports, include:

```typescript
const sourceTitle = reportHasSourceCacheMiss(state.status === 'ready' ? state.report : null)
  ? reportSourceCacheMissMessage(state.status === 'ready' ? state.report : null)
  : state.status === 'ready'
    ? state.report.headline || 'Отчёт получен с бэкенда'
    : 'Загружаем отчёт'
```

Use that value in the card title for stock, ads, RNP, P&L, expenses, and week-over-week.

- [ ] **Step 6: Run frontend tests**

Run from `D:\ogni-frontend\frontend`: `npm test -- --run src/features/vella-parity/reportSourceCacheMiss.test.ts`

Expected: PASS.

Run from `D:\ogni-frontend\frontend`: `npx tsc -b --noEmit`

Expected: PASS.

- [ ] **Step 7: Commit frontend changes**

```powershell
Set-Location D:\ogni-frontend\frontend
git add src/features/vella-parity/VellaHtmlParityPage.tsx src/features/vella-parity/reportSourceCacheMiss.test.ts
git commit -m "feat: show report source cache miss state"
```

---

