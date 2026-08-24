import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const projectRoot = path.resolve(frontendRoot, '..')
const outputRoot = path.resolve(projectRoot, 'outputs', 'vella-react-smoke-2026-05-09')
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4178'
const shouldStartPreview = !process.env.VELLA_BASE_URL

async function waitForServer(url, timeoutMs = 30_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

async function main() {
  let server
  if (shouldStartPreview) {
    if (!existsSync(path.join(frontendRoot, 'dist'))) {
      throw new Error('frontend/dist is missing. Run npm --prefix frontend run build first.')
    }
    server = spawn('npx', ['vite', 'preview', '--host', '127.0.0.1', '--port', '4178', '--strictPort'], {
      cwd: frontendRoot,
      stdio: 'pipe',
    })
    await waitForServer(baseUrl)
  }

  await mkdir(outputRoot, { recursive: true })
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
  const results = []

  async function step(name, fn) {
    try {
      await fn()
      results.push({ name, ok: true })
    } catch (error) {
      results.push({ name, ok: false, error: error instanceof Error ? error.message : String(error) })
    }
  }

  await page.goto(`${baseUrl}/internal/vella-react/repricer`, { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(outputRoot, '01-repricer-default.png'), fullPage: true })

  await step('repricer has no iframe', async () => {
    const iframeCount = await page.locator('iframe').count()
    if (iframeCount !== 0) throw new Error(`Expected 0 iframes, got ${iframeCount}`)
  })

  await step('repricer filters and custom select work', async () => {
    await page.getByPlaceholder('Артикул или название...').fill('HCBT')
    await page.waitForTimeout(100)
    if (await page.locator('.vs-table tbody tr').count() !== 1) throw new Error('Expected search filter to leave one row')
    await page.getByRole('button', { name: 'Все менеджеры' }).click()
    await page.locator('.vs-select-option').filter({ hasText: 'Анна П.' }).click()
    if (await page.locator('.vs-table tbody tr').count() !== 1) throw new Error('Expected manager dropdown to keep one matching row')
  })

  await step('repricer saved views and density work', async () => {
    await page.getByPlaceholder('Артикул или название...').fill('')
    await page.locator('.vs-select-trigger').filter({ hasText: 'Анна П.' }).click()
    await page.locator('.vs-select-option').filter({ hasText: 'Все менеджеры' }).click()
    await page.getByRole('button', { name: /Все/ }).first().click()
    await page.locator('.vr-saved-views-left').getByRole('button', { name: /Loss margin/ }).click()
    const rows = await page.locator('.vs-table tbody tr').count()
    if (rows < 1) throw new Error('Expected Loss margin saved view to show rows')
    await page.getByRole('button', { name: 'Компактно' }).click()
    const density = await page.evaluate(() => localStorage.getItem('vella-density'))
    if (density !== 'compact') throw new Error(`Expected compact density, got ${density}`)
    await page.getByRole('button', { name: /^Все/ }).first().click()
  })

  await step('repricer inline price edit changes visible value', async () => {
    await page.getByRole('button', { name: /2 100 ₽/ }).first().click()
    const input = page.locator('.vs-inline-edit input')
    await input.fill('2220')
    await input.press('Enter')
    await page.getByText('2 220 ₽').waitFor()
  })

  await step('repricer column picker hides margin', async () => {
    await page.getByRole('button', { name: /Колонки/ }).click()
    await page.locator('.vs-dropdown-item').filter({ hasText: 'margin' }).click()
    await page.keyboard.press('Escape')
    if (await page.locator('.vs-table th').filter({ hasText: 'Маржа' }).count()) throw new Error('Expected margin column hidden')
  })

  await step('repricer drawer tabs and escape close', async () => {
    await page.locator('.vr-sku-cell').first().click()
    await page.locator('.vs-drawer-content').waitFor()
    await page.getByRole('button', { name: 'Правила' }).click()
    await page.locator('.vs-drawer-content').getByText('Guardrail', { exact: true }).waitFor()
    await page.keyboard.press('Escape')
    await page.locator('.vs-drawer-content').waitFor({ state: 'hidden' })
  })

  await step('repricer pmin preview and shortcuts modal work', async () => {
    await page.getByRole('button', { name: /Задать P_min/ }).click()
    await page.getByText(/BulkActionPreview: текущий\/new P_min/).waitFor()
    await page.keyboard.press('Escape')
    await page.keyboard.press('?')
    await page.getByText('Горячие клавиши').waitFor()
    await page.getByText('Alt+1...6').waitFor()
    await page.keyboard.press('Escape')
  })

  await step('repricer modal closes by outside click', async () => {
    await page.getByRole('button', { name: /Применить цены/ }).click()
    await page.locator('.vs-modal-content').waitFor()
    await page.mouse.click(20, 20)
    await page.locator('.vs-modal-content').waitFor({ state: 'hidden' })
  })

  await page.screenshot({ path: path.join(outputRoot, '02-repricer-after-actions.png'), fullPage: true })

  await page.goto(`${baseUrl}/internal/vella-react/reports/ads`, { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(outputRoot, '03-reports-ads.png'), fullPage: true })

  await step('reports route has no iframe and position first', async () => {
    const iframeCount = await page.locator('iframe').count()
    if (iframeCount !== 0) throw new Error(`Expected 0 iframes, got ${iframeCount}`)
    const firstHeader = await page.locator('.vs-table th').first().innerText()
    if (!firstHeader.includes('Позиция')) throw new Error(`Expected first report column Позиция, got ${firstHeader}`)
  })

  await step('reports export downloads file', async () => {
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: /Скачать XLS/ }).click()
    const download = await downloadPromise
    if (!download.suggestedFilename().endsWith('.xls')) throw new Error(`Unexpected filename ${download.suggestedFilename()}`)
  })

  await page.goto(`${baseUrl}/internal/vella-react/notifications`, { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(outputRoot, '04-notifications.png'), fullPage: true })

  await step('notifications detail and report download work', async () => {
    await page.getByText('Excel-отчёт готов к скачиванию').click()
    await page.getByText('Файл отчёта').waitFor()
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: /Скачать ещё раз/ }).click()
    const download = await downloadPromise
    if (!download.suggestedFilename().endsWith('.xls')) throw new Error(`Unexpected filename ${download.suggestedFilename()}`)
  })

  await step('calendar and notification popovers close by escape', async () => {
    await page.locator('.vs-top-actions').getByRole('button', { name: /25.04/ }).click()
    await page.locator('.vs-calendar').waitFor()
    await page.keyboard.press('Escape')
    await page.locator('.vs-calendar').waitFor({ state: 'hidden' })
    await page.locator('.vs-top-actions').getByRole('button', { name: 'Уведомления', exact: true }).click()
    await page.locator('.vr-popover-list').waitFor()
    await page.keyboard.press('Escape')
    await page.locator('.vr-popover-list').waitFor({ state: 'hidden' })
  })

  await browser.close()
  server?.kill('SIGTERM')

  const failed = results.filter((result) => !result.ok)
  await writeFile(path.join(outputRoot, 'smoke.json'), JSON.stringify({ baseUrl, results }, null, 2))
  if (failed.length) {
    console.error(JSON.stringify(failed, null, 2))
    process.exit(1)
  }
  console.log(`Vella React smoke passed: ${outputRoot}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
