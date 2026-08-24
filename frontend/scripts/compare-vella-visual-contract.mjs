import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const frontendRoot = process.cwd()
const projectRoot = path.resolve(frontendRoot, '..')
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const outputRoot = path.resolve(projectRoot, 'outputs', `vella-visual-contract-${stamp}`)
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4176'
const shouldStartPreview = !process.env.VELLA_BASE_URL
const strict = process.argv.includes('--strict')

const referenceUrl = `${baseUrl}/vella-production.html?tab=products`
const previewUrl = process.env.VELLA_PREVIEW_PATH
  ? `${baseUrl}${process.env.VELLA_PREVIEW_PATH}`
  : `${baseUrl}/internal/vella-react/repricer`

const probes = [
  {
    name: 'root typography',
    reference: 'body',
    preview: '.vella-html-runtime',
    properties: ['fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing'],
  },
  {
    name: 'SKU typography',
    reference: '.sku',
    preview: '.sku',
    properties: ['fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing', 'color'],
  },
  {
    name: 'brand typography',
    reference: '.logo-name',
    preview: '.logo-name',
    properties: ['fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing', 'color'],
    optional: true,
  },
  {
    name: 'topbar layout',
    reference: '.topbar',
    preview: '.topbar',
    properties: ['height', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'],
  },
  {
    name: 'sidebar layout',
    reference: '.sidebar',
    preview: '.sidebar',
    properties: ['width', 'backgroundColor', 'color'],
  },
  {
    name: 'toolbar search',
    reference: '.search',
    preview: '.search',
    properties: ['borderRadius', 'fontSize', 'backgroundColor', 'borderTopColor'],
  },
  {
    name: 'table header',
    reference: 'th',
    preview: 'th',
    properties: ['fontSize', 'fontWeight', 'letterSpacing', 'textTransform', 'paddingTop', 'paddingBottom', 'color'],
  },
  {
    name: 'bulk action bar',
    reference: '.bulk-bar',
    preview: '.bulk-bar',
    properties: ['height', 'borderRadius', 'backgroundColor', 'color'],
    optional: true,
  },
]

const layoutProbes = [
  { name: 'sidebar width', reference: '.sidebar', preview: '.sidebar', dimension: 'width' },
  { name: 'topbar height', reference: '.topbar', preview: '.topbar', dimension: 'height' },
  { name: 'table row height', reference: '#mainTable tbody tr', preview: '#mainTable tbody tr', dimension: 'height' },
]

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitForHttp(url, timeoutMs = 20_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // keep polling
    }
    await sleep(250)
  }
  throw new Error(`Timed out waiting for ${url}`)
}

function startPreviewServer() {
  const distHtml = path.join(frontendRoot, 'dist', 'index.html')
  if (!existsSync(distHtml)) {
    throw new Error('dist/index.html is missing. Run npm run build first.')
  }

  const child = spawn(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4176', '--strictPort'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  return child
}

async function readComputed(page, selector, properties) {
  return page.evaluate(
    ({ selector: targetSelector, properties: targetProperties }) => {
      const element = document.querySelector(targetSelector)
      if (!element) return null
      const style = window.getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return {
        rect: {
          width: Math.round(rect.width * 100) / 100,
          height: Math.round(rect.height * 100) / 100,
          top: Math.round(rect.top * 100) / 100,
          left: Math.round(rect.left * 100) / 100,
        },
        styles: Object.fromEntries(targetProperties.map((property) => [property, style[property]])),
      }
    },
    { selector, properties },
  )
}

function normalize(value) {
  return String(value || '')
    .replace(/"/g, "'")
    .replace(/\s+/g, ' ')
    .trim()
}

function equivalent(property, reference, preview) {
  if (property === 'fontFamily') {
    const left = normalize(reference).split(',')[0]?.trim()
    const right = normalize(preview).split(',')[0]?.trim()
    return left === right
  }
  return normalize(reference) === normalize(preview)
}

async function main() {
  let server = null
  if (shouldStartPreview) {
    server = startPreviewServer()
    await waitForHttp(baseUrl)
  }

  await mkdir(outputRoot, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const reference = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const preview = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  try {
    await reference.goto(referenceUrl, { waitUntil: 'networkidle' })
    await preview.goto(previewUrl, { waitUntil: 'networkidle' })
    await reference.waitForTimeout(600)
    await preview.waitForTimeout(600)

    await reference.screenshot({ path: path.join(outputRoot, 'reference-products-1440.png'), fullPage: false })
    await preview.screenshot({ path: path.join(outputRoot, 'preview-repricer-1440.png'), fullPage: false })

    const checks = []
    for (const probe of probes) {
      const referenceStyle = await readComputed(reference, probe.reference, probe.properties)
      const previewStyle = await readComputed(preview, probe.preview, probe.properties)
      const missing = !referenceStyle || !previewStyle
      const diffs = missing
        ? [{ property: 'selector', reference: Boolean(referenceStyle), preview: Boolean(previewStyle) }]
        : probe.properties
          .filter((property) => !equivalent(property, referenceStyle.styles[property], previewStyle.styles[property]))
          .map((property) => ({
            property,
            reference: referenceStyle.styles[property],
            preview: previewStyle.styles[property],
          }))

      checks.push({
        type: 'computed-style',
        name: probe.name,
        referenceSelector: probe.reference,
        previewSelector: probe.preview,
        optional: Boolean(probe.optional),
        pass: probe.optional ? diffs.length === 0 || missing : diffs.length === 0,
        reference: referenceStyle,
        preview: previewStyle,
        diffs,
      })
    }

    for (const probe of layoutProbes) {
      const referenceStyle = await readComputed(reference, probe.reference, [])
      const previewStyle = await readComputed(preview, probe.preview, [])
      const referenceValue = referenceStyle?.rect?.[probe.dimension] ?? null
      const previewValue = previewStyle?.rect?.[probe.dimension] ?? null
      checks.push({
        type: 'layout',
        name: probe.name,
        referenceSelector: probe.reference,
        previewSelector: probe.preview,
        pass: referenceValue !== null && previewValue !== null && Math.abs(referenceValue - previewValue) <= 1,
        reference: referenceValue,
        preview: previewValue,
      })
    }

    const failures = checks.filter((check) => !check.pass && !check.optional)
    const report = {
      generatedAt: new Date().toISOString(),
      strict,
      referenceUrl,
      previewUrl,
      status: failures.length === 0 ? 'pass' : 'fail',
      failureCount: failures.length,
      checks,
      screenshots: ['reference-products-1440.png', 'preview-repricer-1440.png'],
    }

    await writeFile(path.join(outputRoot, 'visual-contract-report.json'), JSON.stringify(report, null, 2))
    console.log(`Vella visual contract: ${report.status}`)
    console.log(`Report: ${path.relative(projectRoot, path.join(outputRoot, 'visual-contract-report.json'))}`)
    for (const failure of failures.slice(0, 12)) {
      console.log(`- ${failure.name}: ${failure.type}`)
      if ('diffs' in failure) {
        for (const diff of failure.diffs.slice(0, 4)) {
          console.log(`  ${diff.property}: reference=${diff.reference} preview=${diff.preview}`)
        }
      } else {
        console.log(`  reference=${failure.reference} preview=${failure.preview}`)
      }
    }

    if (strict && failures.length > 0) process.exitCode = 1
  } finally {
    await browser.close()
    if (server) server.kill('SIGTERM')
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
