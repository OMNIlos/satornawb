import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { expect, it } from 'vitest'

it('shows the live Avito notifications page instead of a blank tab', async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
    define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)),
      formats: ['iife'], name: 'AvitoNotificationsTest',
    } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const bundle = outputs.flatMap(output => 'output' in output ? output.output : [])
    .find(output => output.type === 'chunk' && output.isEntry)
  if (!bundle || bundle.type !== 'chunk') throw new Error('Missing Avito notifications test bundle')

  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block' })
    let notificationRequests = 0
    await page.route('**/*', route => {
      const url = new URL(route.request().url())
      if (url.origin === 'http://satorna.test' && url.pathname === '/avito/notifications') {
        return route.fulfill({ contentType: 'text/html', body: '<div id="root"></div>' })
      }
      if (url.origin === 'http://satorna.test' && url.pathname === '/api/v1/avito/notifications') {
        notificationRequests++
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
          status: 'synced', summary: { total: 0, unread: 0, critical: 0, warning: 0, info: 0, sectionsBlocked: 0 },
          items: [], rulesRows: [], recipientRows: [], channelRows: [], historyRows: [],
        }) })
      }
      return route.abort()
    })
    await page.goto('http://satorna.test/avito/notifications')
    await page.addScriptTag({ content: bundle.code })
    const surface = page.locator('#tab-notifications')
    await surface.getByText('Уведомлений Авито пока нет', { exact: true }).waitFor({ state: 'visible', timeout: 15_000 })
    expect(await surface.isVisible()).toBe(true)
    expect(notificationRequests).toBe(1)
  } finally { await browser.close() }
}, 60_000)
