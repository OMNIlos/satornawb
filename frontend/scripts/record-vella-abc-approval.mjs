import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const projectRoot = path.resolve(frontendRoot, '..')
const manifestPath = path.join(projectRoot, 'docs', 'react-migration', 'wb-reports-abc-approval.manifest.json')
const approvalPackPath = path.join(projectRoot, 'docs', 'react-migration', 'reviews', 'wb-reports-abc-2026-05-31-approval.md')
const decisionHeading = '## Decision'
const recordCommand = 'VELLA_APPROVAL_SIGNAL="<exact user approval text>" npm --prefix frontend run review:vella-abc-approval:record'
const dryRunCommand = 'VELLA_APPROVAL_SIGNAL="<test approval text>" VELLA_APPROVAL_DRY_RUN=1 npm --prefix frontend run review:vella-abc-approval:record'

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

function requireApprovalSignal() {
  const signal = process.env.VELLA_APPROVAL_SIGNAL?.trim()
  if (!signal) {
    throw new Error('Set VELLA_APPROVAL_SIGNAL to the exact user approval text before recording approval.')
  }
  return signal
}

function buildDecisionSection(signal, approvedAt) {
  return `${decisionHeading}

Status: **approved for promotion review**.

Approval signal: \`${signal}\`.

Approved at: \`${approvedAt}\`.

Production route still must not be switched automatically. The next action is either a separate explicit promotion patch for \`/wb/reports/abc\` after rerunning \`review:vella-abc-approval:refresh\`, or starting the next report screen under the same parity gates.
`
}

function updateDecisionSection(markdown, signal, approvedAt) {
  const nextSection = buildDecisionSection(signal, approvedAt)
  const start = markdown.indexOf(decisionHeading)
  if (start === -1) {
    return `${markdown.trimEnd()}\n\n${nextSection}\n`
  }

  const nextHeading = markdown.indexOf('\n## ', start + decisionHeading.length)
  if (nextHeading === -1) {
    return `${markdown.slice(0, start).trimEnd()}\n\n${nextSection}\n`
  }

  return `${markdown.slice(0, start).trimEnd()}\n\n${nextSection}\n${markdown.slice(nextHeading + 1).trimStart()}`
}

function isDryRun() {
  return process.env.VELLA_APPROVAL_DRY_RUN === '1'
}

async function runVerifier(stage) {
  const verification = await runCommand(process.execPath, ['scripts/verify-vella-abc-approval.mjs'])
  if (verification.code !== 0) {
    throw new Error(`ABC approval verification failed ${stage}; approval was not recorded.`)
  }
}

async function main() {
  const signal = requireApprovalSignal()
  const dryRun = isDryRun()

  await runVerifier('before recording')

  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'))
  const alreadyApproved = manifest.status === 'approved_for_promotion_review'
  if (alreadyApproved && manifest.manualReview?.approvalSignal !== signal) {
    throw new Error('Manifest already has a different approval signal; approval was not recorded.')
  }
  if (manifest.status !== 'pending_manual_approval' && !alreadyApproved) {
    throw new Error(`Unexpected manifest status: ${manifest.status}`)
  }
  if (manifest.productionSwitchAllowed !== false || manifest.productionOwner !== 'VellaStaticPage') {
    throw new Error('Production switch guard is not intact; approval was not recorded.')
  }

  const approvedAt = manifest.manualReview?.approvedAt && alreadyApproved
    ? manifest.manualReview.approvedAt
    : new Date().toISOString()
  manifest.status = 'approved_for_promotion_review'
  manifest.productionSwitchAllowed = false
  manifest.manualReview.approvalSignal = signal
  manifest.manualReview.approvedAt = approvedAt
  manifest.manualReview.approvedBy = process.env.VELLA_APPROVED_BY?.trim() || 'user'
  manifest.manualReview.recordCommand = recordCommand
  manifest.manualReview.dryRunCommand = dryRunCommand
  manifest.blockedActionsUntilManualApproval = []
  manifest.blockedActionsUntilExplicitPromotionPatch = [
    'Switch /wb/reports/abc from VellaStaticPage to React candidate without a separate promotion patch',
    'Use ABC approval as approval for other report screens',
    'Promote if review:vella-abc-approval:refresh no longer passes',
  ]

  const nextManifest = `${JSON.stringify(manifest, null, 2)}\n`
  if (!nextManifest.includes('"status": "approved_for_promotion_review"') || !nextManifest.includes(signal)) {
    throw new Error('Approval manifest update did not include the expected approval fields.')
  }

  if (existsSync(approvalPackPath)) {
    let approvalPack = await readFile(approvalPackPath, 'utf8')
    approvalPack = updateDecisionSection(approvalPack, signal, approvedAt)
    if (!approvalPack.includes('Status: **approved for promotion review**.') || !approvalPack.includes(`Approval signal: \`${signal}\`.`)) {
      throw new Error('Approval pack update did not include the expected decision fields.')
    }
    if (!dryRun) {
      await writeFile(approvalPackPath, approvalPack)
    }
  }

  if (dryRun) {
    console.log('Vella ABC manual approval dry run passed.')
    console.log('No approval status was recorded.')
    return
  }

  await writeFile(manifestPath, nextManifest)
  await runVerifier('after recording')

  console.log('Vella ABC manual approval recorded.')
  console.log(`Approved at: ${approvedAt}`)
  console.log('Production switch remains blocked until a separate promotion patch.')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
