import { useEffect, useMemo, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { vellaProductionHtml, vellaProductionSnapshotHash } from './vellaProductionSnapshot.generated'

let vellaInlineScriptsExecuted = false

function extractFirstMatch(source: string, pattern: RegExp) {
  return source.match(pattern)?.[1] ?? ''
}

function extractAllMatches(source: string, pattern: RegExp) {
  return Array.from(source.matchAll(pattern), (match) => match[0]).join('\n')
}

function extractScriptBodies(source: string) {
  return Array.from(source.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi), (match) => match[1]).filter(Boolean)
}

function stripScripts(source: string) {
  return source.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
}

function extractBodyHtml(source: string) {
  const bodyOpen = source.match(/<body[^>]*>/i)
  if (!bodyOpen || bodyOpen.index == null) return ''
  const bodyStart = bodyOpen.index + bodyOpen[0].length
  const bodyEnd = source.lastIndexOf('</body>')
  return bodyEnd > bodyStart ? source.slice(bodyStart, bodyEnd) : source.slice(bodyStart)
}

function runVellaRouteBootstrap() {
  window.setTimeout(() => {
    const vellaWindow = window as typeof window & {
      resolveInitialTab?: () => string
      _pushNav?: (tab: string) => void
      _goSubtabSilent?: (tab: string, options?: Record<string, unknown>) => void
      renderTable?: () => void
      enhanceReportsDemo?: () => void
    }

    try {
      const initialTab = vellaWindow.resolveInitialTab?.()
      if (initialTab) {
        vellaWindow._pushNav?.(initialTab)
        vellaWindow._goSubtabSilent?.(initialTab, { preserveDigestMode: true })
      }
      vellaWindow.renderTable?.()
      vellaWindow.enhanceReportsDemo?.()
    } catch (error) {
      console.error('Vella parity bootstrap failed', error)
    }
  }, 0)
}

export function VellaHtmlSnapshotPage() {
  const location = useLocation()
  const rootRef = useRef<HTMLDivElement>(null)

  const snapshot = useMemo(() => {
    const head = extractFirstMatch(vellaProductionHtml, /<head[^>]*>([\s\S]*?)<\/head>/i)
    const body = extractBodyHtml(vellaProductionHtml)
    return {
      headAssets: [
        extractAllMatches(head, /<link\b[^>]*>/gi),
        extractAllMatches(head, /<style[^>]*>[\s\S]*?<\/style>/gi),
      ].filter(Boolean).join('\n'),
      bodyHtml: stripScripts(body),
      scripts: extractScriptBodies(body),
      title: extractFirstMatch(head, /<title[^>]*>([\s\S]*?)<\/title>/i) || 'Satorna',
    }
  }, [])

  useEffect(() => {
    document.title = snapshot.title
    const template = document.createElement('template')
    template.innerHTML = snapshot.headAssets
    const assets = Array.from(template.content.children)
    assets.forEach((node) => {
      node.setAttribute('data-vella-parity-asset', vellaProductionSnapshotHash)
      document.head.appendChild(node)
    })
    return () => {
      document.querySelectorAll(`[data-vella-parity-asset="${vellaProductionSnapshotHash}"]`).forEach((node) => node.remove())
    }
  }, [snapshot.headAssets, snapshot.title])

  useEffect(() => {
    if (!vellaInlineScriptsExecuted) {
      snapshot.scripts.forEach((scriptBody) => {
        const script = document.createElement('script')
        script.textContent = scriptBody
        script.dataset.vellaParityScript = vellaProductionSnapshotHash
        document.body.appendChild(script)
      })
      vellaInlineScriptsExecuted = true
    }
    runVellaRouteBootstrap()
  }, [location.pathname, location.search, snapshot.scripts])

  return (
    <div
      key={`${location.pathname}${location.search}`}
      ref={rootRef}
      data-vella-parity-root={vellaProductionSnapshotHash}
      style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        overflow: 'hidden',
        background: 'var(--sidebar-bg)',
        color: 'var(--gray-900)',
        fontSize: 14,
      }}
      dangerouslySetInnerHTML={{ __html: snapshot.bodyHtml }}
    />
  )
}
