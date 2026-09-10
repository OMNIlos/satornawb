import { it, expect } from 'vitest'
import { chromium } from 'playwright'
import { createServer } from 'vite'
import { fileURLToPath } from 'node:url'
import { mkdir } from 'node:fs/promises'

// Synthetic component gate only. All HTTP data are fixtures; provider/API access is denied.
const root = fileURLToPath(new URL('../../../', import.meta.url))
const uid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const at = '2026-09-09T12:00:01.123456Z'
const fixture = `
import React from 'react';
import {createRoot} from 'react-dom/client';
import {AuthContext} from '/src/features/auth/authContext.ts';
import {CanonicalNotificationsIsland,canonicalNotificationsEnabled} from '/src/features/notifications/CanonicalNotificationsIsland.tsx';
import {CanonicalNotificationPreferencesForm} from '/src/features/notifications/NotificationPreferencesForm.tsx';
import {CanonicalReviewDrawer,canonicalReviewSelectionEvent} from '/src/features/wb-reviews/CanonicalReviewDrawer.tsx';
import {canonicalReviewsEnabled} from '/src/features/wb-reviews/canonicalReviewDetail.ts';
const h=React.createElement;
function Fixture(){
 const [tab,setTab]=React.useState('notifications'),[session,setSession]=React.useState(1);
 const auth={accessToken:'synthetic-browser-only',cabinetMe:{activeSession:{sessionId:'synthetic-'+session},organization:{organizationId:1},user:{userId:1,permissions:['reviews:read','reviews:write','reviews:approve']}}};
 return h(AuthContext.Provider,{value:auth},h('h1',null,'Synthetic canonical workflow gate'),
 h('button',{onClick:()=>setTab('notifications')},'Notifications fixture'),
 h('button',{onClick:()=>setTab('reviews')},'Reviews fixture'),
 h('button',{onClick:()=>setSession(x=>x+1)},'New synthetic session'),
 h('p',{'data-flags':String(canonicalNotificationsEnabled)+':'+String(canonicalReviewsEnabled)},'Default-off gates'),
 tab==='notifications'&&canonicalNotificationsEnabled?h(React.Fragment,null,h(CanonicalNotificationsIsland),h(CanonicalNotificationPreferencesForm)):null,
 tab==='reviews'&&canonicalReviewsEnabled?h(React.Fragment,null,h('button',{onClick:()=>{document.getElementById('reviewDrawer').classList.add('open');window.dispatchEvent(new CustomEvent(canonicalReviewSelectionEvent,{detail:'synthetic-review-a'}));}},'Open synthetic review'),h(CanonicalReviewDrawer)):null);
}
createRoot(document.getElementById('root')).render(h(Fixture));`

it('synthetic browser: gates, personal readback/preferences CAS, first manual draft and account/session epochs', async () => {
  const browser = await chromium.launch({ headless: true })
  const screenshots = '/tmp/satorna-canonical-ui-proof'
  await mkdir(screenshots, { recursive: true })
  try {
    for (const enabled of [false, true]) {
      const server = await createServer({ root, configFile: `${root}vite.config.ts`,
        cacheDir: `${screenshots}/vite-cache`,
        define: { 'import.meta.env.VITE_CANONICAL_NOTIFICATIONS_ENABLED': JSON.stringify(String(enabled)),
          'import.meta.env.VITE_CANONICAL_REVIEWS_ENABLED': JSON.stringify(String(enabled)), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
        server: { host: '127.0.0.1', port: 0, strictPort: true },
        plugins: [{ name: 'synthetic-canonical-browser-fixture',
          resolveId(id) { if (id === '/__synthetic.jsx') return '\0synthetic.jsx' },
          load(id) { if (id === '\0synthetic.jsx') return fixture },
          configureServer(vite) { vite.middlewares.use(async (req, res, next) => {
            if (req.url !== '/__synthetic') return next()
            res.setHeader('Content-Type', 'text/html'); res.end(await vite.transformIndexHtml('/__synthetic', '<html><head><title>Synthetic canonical UI</title></head><body><div id="root"></div><aside id="reviewDrawer"><div class="drawer-body"></div></aside><script type="module" src="/__synthetic.jsx"></script></body></html>'))
          }) },
        }],
      })
      await server.listen()
      const address = server.httpServer!.address()
      if (!address || typeof address === 'string') throw new Error('Missing fixture port')
      const origin = `http://127.0.0.1:${address.port}`
      const page = await browser.newPage({ viewport: { width: 1366, height: 900 }, serviceWorkers: 'block' })
      page.setDefaultTimeout(8_000)
      const errors: string[] = [], unexpected: string[] = [], writes: unknown[] = []
      let read = false, markFailure = false, prefConflict = true, preferenceVersion = '1'
      let heldCommand: (() => Promise<void>) | null = null
      page.on('pageerror', error => errors.push(error.message))
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
      const scope = (account: number) => ({ organizationId: 1, marketplaceAccountId: account, marketplace: 'wb' })
      const receipt = () => ({ value: { schemaVersion: 'notification-in-app-receipt-v1', organizationId: 1,
        marketplaceAccountId: 11, eventId: uid(9), recipientMembershipId: 7, readAt: at, dismissedAt: null }, version: '1' })
      try {
        await page.route('**/*', async route => {
          const req = route.request(), url = new URL(req.url())
          const json = (value: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
          if (url.origin !== origin) { unexpected.push(`${req.method()} ${url.origin}${url.pathname}`); return route.abort() }
          if (!url.pathname.startsWith('/api/')) return route.continue()
          const account = Number(url.searchParams.get('marketplace_account_id')) || 11
          if (url.pathname === '/api/v1/cabinet/marketplace-accounts') return json({ data: [11, 12].map(id => ({ marketplaceAccountId: id, provider: 'wb', externalAccountId: `synthetic-seller-${id}`, displayName: `Synthetic WB ${id}`, status: 'active' })) })
          if (url.pathname === '/api/v2/notifications/preferences') {
            if (req.method() === 'PUT') { writes.push(req.postDataJSON()); if (prefConflict) { preferenceVersion = '2'; return json({}, 409) } }
            return json({ schemaVersion: 'notification-preferences-v1', version: preferenceVersion, email: { enabled: true, dailyDigest: false, criticalAlerts: true }, telegram: { enabled: false } })
          }
          if (url.pathname === '/api/v2/reviews/notifications') return json({ schemaVersion: 'review-notification-list-v1', ...scope(account), recipientMembershipId: 7,
            eventIds: account === 11 ? [uid(9)] : [], items: account === 11 ? [{ event: { schemaVersion: 'notification-event-v1', eventId: uid(9), organizationId: 1, marketplaceAccountId: 11, scope: 'account', producer: 'reviews', entityId: uid(1), sourceVersion: '1', kind: 'approval_required', occurredAt: at,
              dedupeKey: 'b6c58324017df7859f2f6779f26f71d19ec304d238a853c508714969e6ddafce', title: 'Ответ на отзыв требует подтверждения', details: 'Проверьте текущую версию черновика в разделе отзывов.', severity: 'info' }, receipt: read ? receipt() : null }] : [],
            nextCursor: null, eventSetVersion: account === 11 ? '1' : '0', capabilities: { canRead: true, canMarkRead: true, canDismiss: true } })
          if (url.pathname === '/api/v2/reviews/notifications/receipts') {
            writes.push(req.postDataJSON()); read = true
            return markFailure ? json({}, 503) : json({ schemaVersion: 'review-notification-receipts-v1', ...scope(11), recipientMembershipId: 7, eventIds: [uid(9)], action: 'read', items: [receipt()] })
          }
          if (url.pathname === '/api/v2/reviews/wb/fact') return json({ schema_version: 'canonical-review-fact-v1', organization_id: 1, marketplace_account_id: account, marketplace: 'wb', external_review_id: 'synthetic-review-a', review_id: uid(1), current_observation_id: uid(2), version: '1', revision: '1', text: `Synthetic fact ${account}`, answered: false, can_answer: true, source_order_state: 'current', content_checksum: 'a'.repeat(64), external_product_id: null, source_created_at: at, source_updated_at: null, source_schema_version: 'v1', normalization_version: 'v1' })
          if (url.pathname === '/api/v2/reviews/local/context') return json({ schemaVersion: 'review-local-context-v1', ...scope(account), actorMembershipId: 7,
            policy: { schemaVersion: 'review-policy-v1', ...scope(account), policyId: uid(3), version: '1', approvalMode: 'manual', templateVersion: 'manual-v1', modelVersion: 'captured-policy-only' }, policyHead: { headId: uid(4), version: '1', policyChecksum: 'b'.repeat(64) },
            review: { reviewId: uid(1), externalReviewId: 'synthetic-review-a', sourceObservationId: uid(2), sourceChecksum: 'a'.repeat(64), text: `Synthetic fact ${account}`, answered: false, canAnswer: true, sourceOrderState: 'current' }, draft: null, workflowHead: null, decision: null })
          if (url.pathname === '/api/v2/reviews/local/history') return json({ schemaVersion: 'review-local-history-v1', ...scope(account), reviewId: uid(1), headId: null, throughVersion: '0', events: [], nextAfterVersion: null })
          if (url.pathname === '/api/v2/reviews/local/commands') {
            const command = req.postDataJSON(); writes.push(command)
            heldCommand = async () => { await json({ schemaVersion: 'review-local-command-result-v1', localCommandId: command.localCommandId, operationKind: command.operationKind, auditEventId: uid(10), completedAt: at, policyId: uid(3), policyVersion: '1', draftId: command.input.draftId, draftRevision: '1', decisionId: null, headId: uid(11), headVersion: '1' }).catch(() => {}) }
            return
          }
          unexpected.push(`${req.method()} ${url.pathname}`); return route.abort()
        })
        await page.goto(`${origin}/__synthetic`)
        await page.getByText('Synthetic canonical workflow gate', { exact: true }).waitFor()
        expect(await page.title()).toBe('Synthetic canonical UI')
        expect(page.url()).toBe(`${origin}/__synthetic`)
        expect(await page.locator('vite-error-overlay').count()).toBe(0)
        if (!enabled) {
          expect(await page.locator('[data-flags="false:false"]').count()).toBe(1)
          expect(await page.locator('[data-canonical-notifications]').count()).toBe(0)
          await page.getByRole('button', { name: 'Reviews fixture', exact: true }).click()
          expect(await page.getByRole('button', { name: 'Open synthetic review' }).count()).toBe(0)
          expect(writes).toEqual([])
        } else {
          await page.getByRole('combobox', { name: 'Аккаунт Wildberries' }).selectOption('11')
          await page.getByRole('cell', { name: /Ответ на отзыв требует подтверждения/ }).click()
          const mark = page.getByRole('button', { name: 'Пометить прочитанным', exact: true })
          await mark.click(); await page.waitForFunction(() => document.querySelector('.notif-detail-body')?.textContent?.includes('Прочитано:'))
          expect(await mark.isDisabled()).toBe(true)
          await page.getByRole('combobox', { name: 'Аккаунт Wildberries' }).selectOption('12')
          await page.getByText('Уведомлений об отзывах пока нет.', { exact: true }).waitFor()
          read = false; markFailure = true
          await page.getByRole('combobox', { name: 'Аккаунт Wildberries' }).selectOption('11')
          await mark.click(); await page.getByText(/Результат.*неизвестен/).waitFor()
          expect(await mark.isDisabled()).toBe(true)
          await page.getByRole('button', { name: 'Обновить список', exact: true }).click()
          await page.waitForFunction(() => document.querySelector('.notif-detail-body')?.textContent?.includes('Прочитано:'))
          expect(writes.filter((w: any) => w.action === 'read')).toHaveLength(2)
          await page.getByRole('checkbox', { name: 'Ежедневный дайджест', exact: true }).check()
          await page.getByRole('button', { name: 'Сохранить настройки уведомлений', exact: true }).click()
          await page.getByText(/Настройки изменились/).waitFor()
          expect(await page.getByRole('checkbox', { name: 'Ежедневный дайджест', exact: true }).isDisabled()).toBe(true)
          expect(writes.filter((w: any) => w.schemaVersion === 'notification-preferences-update-v1')).toHaveLength(1)
          prefConflict = false
          await page.getByRole('button', { name: 'Перечитать настройки', exact: true }).click()
          await page.waitForFunction(() => !document.querySelector('fieldset')?.disabled)
          expect(await page.getByRole('checkbox', { name: 'Ежедневный дайджест', exact: true }).isChecked()).toBe(false)
          await page.screenshot({ path: `${screenshots}/notifications.png`, fullPage: true })
          await page.getByRole('button', { name: 'Reviews fixture', exact: true }).click()
          await page.getByRole('button', { name: 'Open synthetic review' }).click()
          const draft = page.getByRole('textbox', { name: 'Ручной черновик ответа' })
          await draft.fill('Synthetic human first draft')
          await page.getByRole('button', { name: 'Создать ручной черновик', exact: true }).click()
          await page.waitForFunction(() => document.body.textContent?.includes('Читаем или сохраняем'))
          await page.getByRole('combobox', { name: 'Аккаунт Wildberries' }).selectOption('12')
          await draft.fill('Synthetic account B')
          await page.getByRole('combobox', { name: 'Аккаунт Wildberries' }).selectOption('11')
          await draft.fill('Keep current account A draft')
          expect(heldCommand).not.toBeNull(); await heldCommand!()
          expect(await draft.inputValue()).toBe('Keep current account A draft')
          expect(await page.getByText(/Локальное изменение сохранено/).count()).toBe(0)
          const commands = writes.filter((w: any) => w.schemaVersion === 'review-local-command-v1') as any[]
          expect(commands).toHaveLength(1)
          expect(commands[0].input).toMatchObject({ expectedHeadVersion: '0', expectedDraftRevision: '0', generation: { mode: 'manual', actorMembershipId: 7, modelVersion: 'captured-policy-only' } })
          expect(commands[0].input.generation).not.toHaveProperty('previousDraftId')
          await page.getByRole('button', { name: 'New synthetic session', exact: true }).click()
          await page.waitForFunction(() => !document.querySelector('textarea'))
          expect(await page.getByText('Keep current account A draft').count()).toBe(0)
          await page.getByRole('combobox', { name: 'Аккаунт Wildberries' }).selectOption('11')
          await draft.fill('New session draft')
          await page.screenshot({ path: `${screenshots}/reviews.png`, fullPage: true })
          await page.setViewportSize({ width: 390, height: 844 })
          await page.screenshot({ path: `${screenshots}/reviews-mobile.png`, fullPage: true })
        }
        // Chromium reports the two deliberately injected HTTP failures in console.
        // No exception, overlay, external request, or additional console error is accepted.
        expect(errors).toEqual(enabled ? [
          'Failed to load resource: the server responded with a status of 503 (Service Unavailable)',
          'Failed to load resource: the server responded with a status of 409 (Conflict)',
        ] : [])
        expect(await page.locator('vite-error-overlay').count()).toBe(0)
        expect(unexpected).toEqual([])
      } catch (failure) { throw new Error(`${String(failure)}; browser errors=${JSON.stringify(errors)}; DOM=${(await page.locator('body').innerText()).slice(0, 1200)}`) }
      finally { await page.close(); await server.close() }
    }
  } finally { await browser.close() }
}, 90_000)
