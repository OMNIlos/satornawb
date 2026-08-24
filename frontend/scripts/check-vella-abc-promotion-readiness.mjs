import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const projectRoot = path.resolve(frontendRoot, '..')
const latestReviewRoot = path.join(projectRoot, 'outputs', 'vella-approval-wb-reports-abc-latest')
const readinessReportPath = path.join(latestReviewRoot, 'promotion-readiness-report.json')
const manifestPath = process.env.VELLA_ABC_APPROVAL_MANIFEST_PATH
  ? path.resolve(projectRoot, process.env.VELLA_ABC_APPROVAL_MANIFEST_PATH)
  : path.join(projectRoot, 'docs', 'react-migration', 'wb-reports-abc-approval.manifest.json')

function relativeFromProject(filePath) {
  return path.relative(projectRoot, filePath)
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, 'utf8'))
}

function runCommand(command, args) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd: frontendRoot,
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    let output = ''
    child.stdout.on('data', (chunk) => {
      const text = chunk.toString()
      output += text
      process.stdout.write(text)
    })
    child.stderr.on('data', (chunk) => {
      const text = chunk.toString()
      output += text
      process.stderr.write(text)
    })
    child.on('close', (code) => resolve({ code, output }))
  })
}

function collectPreconditions(manifest, verificationReport) {
  return [
    {
      name: 'manual approval recorded',
      pass: manifest.status === 'approved_for_promotion_review',
      detail: manifest.status,
    },
    {
      name: 'approval signal present',
      pass: Boolean(manifest.manualReview?.approvalSignal),
      detail: manifest.manualReview?.approvalSignal ? 'present' : 'missing',
    },
    {
      name: 'approvedAt present',
      pass: Boolean(manifest.manualReview?.approvedAt),
      detail: manifest.manualReview?.approvedAt || 'missing',
    },
    {
      name: 'production switch still blocked',
      pass: manifest.productionSwitchAllowed === false,
      detail: String(manifest.productionSwitchAllowed),
    },
    {
      name: 'production owner still static before patch',
      pass: manifest.productionOwner === 'VellaStaticPage',
      detail: manifest.productionOwner,
    },
    {
      name: 'visual gate passing',
      pass: manifest.gates?.defaultVisual?.status === 'pass',
      detail: manifest.gates?.defaultVisual?.status || 'missing',
    },
    {
      name: 'machine contract passing',
      pass: manifest.gates?.machineContract?.status === 'pass',
      detail: manifest.gates?.machineContract?.status || 'missing',
    },
    {
      name: 'interaction gate passing',
      pass: manifest.gates?.interaction?.status === 'pass',
      detail: manifest.gates?.interaction?.status || 'missing',
    },
    {
      name: 'approval verifier passing',
      pass: verificationReport.status === 'pass',
      detail: verificationReport.status,
    },
  ]
}

async function writeReport(report) {
  await mkdir(latestReviewRoot, { recursive: true })
  await writeFile(readinessReportPath, `${JSON.stringify(report, null, 2)}\n`)
}

async function main() {
  const verification = await runCommand(process.execPath, ['scripts/verify-vella-abc-approval.mjs'])
  const verificationReportPath = path.join(latestReviewRoot, 'verification-report.json')
  const verificationReport = existsSync(verificationReportPath)
    ? await readJson(verificationReportPath)
    : { status: verification.code === 0 ? 'pass' : 'fail' }

  if (verification.code !== 0) {
    await writeReport({
      generatedAt: new Date().toISOString(),
      status: 'blocked_verification_failed',
      promotionAllowed: false,
      verificationReport: relativeFromProject(verificationReportPath),
    })
    console.error('Vella ABC promotion readiness: blocked_verification_failed')
    console.error(`Report: ${readinessReportPath}`)
    process.exit(1)
  }

  const manifest = await readJson(manifestPath)
  const preconditions = collectPreconditions(manifest, verificationReport)
  const failed = preconditions.filter((item) => !item.pass)
  const status = failed.length === 0 ? 'ready_for_explicit_promotion_patch' : 'blocked_pending_preconditions'
  const report = {
    generatedAt: new Date().toISOString(),
    status,
    promotionAllowed: status === 'ready_for_explicit_promotion_patch',
    productionRoute: manifest.productionRoute,
    requiredNextAction: status === 'ready_for_explicit_promotion_patch'
      ? 'Create a separate explicit patch that switches /wb/reports/abc from VellaStaticPage to the React parity candidate.'
      : 'Do not switch production. Resolve failed preconditions first.',
    manifest: relativeFromProject(manifestPath),
    verificationReport: relativeFromProject(verificationReportPath),
    preconditions,
  }

  await writeReport(report)

  if (status !== 'ready_for_explicit_promotion_patch') {
    console.error(`Vella ABC promotion readiness: ${status}`)
    console.error(`Failed preconditions: ${failed.map((item) => item.name).join(', ')}`)
    console.error(`Report: ${readinessReportPath}`)
    process.exit(1)
  }

  console.log('Vella ABC promotion readiness: ready_for_explicit_promotion_patch')
  console.log(`Report: ${readinessReportPath}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
