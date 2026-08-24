import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

const publicDir = path.resolve(import.meta.dirname, '../public')
const server = createServer(async (request, response) => {
  try {
    const pathname = new URL(request.url ?? '/', 'http://localhost').pathname
    const file = pathname === '/' ? 'vella-production.html' : pathname.slice(1)
    response.setHeader('Content-Type', 'text/html; charset=utf-8')
    response.end(await readFile(path.join(publicDir, file)))
  } catch {
    response.writeHead(404).end('Not found')
  }
})

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
const address = server.address()
if (!address || typeof address === 'string') throw new Error('QA server did not start')

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

try {
  await page.goto(`http://127.0.0.1:${address.port}/vella-production.html?tab=avito-overview`)
  const privacyLink = page.getByRole('link', { name: 'Политика конфиденциальности' })
  await privacyLink.waitFor({ state: 'visible', timeout: 3000 })

  const popupPromise = page.waitForEvent('popup')
  await privacyLink.click()
  const privacyPage = await popupPromise
  await privacyPage.waitForLoadState('domcontentloaded')

  await privacyPage.getByRole('heading', { level: 1, name: 'Политика конфиденциальности' }).waitFor()
  const body = await privacyPage.locator('body').innerText()
  if (!body.includes('Satorna Avito Orders')) throw new Error('Product name is missing')
  if (!body.includes('ИП Масорина Ирина Сергеевна')) throw new Error('Operator is missing')
  if (!body.includes('masorin777@yandex.ru')) throw new Error('Contact email is missing')
  if (await privacyPage.getByRole('heading', { level: 2 }).count() !== 12) {
    throw new Error('Privacy policy must contain 12 sections')
  }
} finally {
  await browser.close()
  server.close()
}
