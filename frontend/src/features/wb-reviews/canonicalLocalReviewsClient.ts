import { buildApiUrl } from '@/lib/api'
import {
  buildCanonicalReviewHistoryPath, buildCanonicalReviewLocalContextPath,
  canonicalReviewLocalCommandPath, encodeCanonicalReviewLocalCommand,
  parseCanonicalReviewHistory, parseCanonicalReviewLocalContext, parseCanonicalReviewLocalResult,
  type CanonicalReviewHistoryRequest, type CanonicalReviewLocalCommand, type CanonicalReviewScope,
} from './canonicalLocalReviews'

export type LocalReviewFailure = {
  state: 'invalid-request' | 'unauthenticated' | 'no-access' | 'not-found' | 'conflict'
    | 'unavailable' | 'invalid-response' | 'stale'
  // A lost response/abort is not evidence that a POST rolled back.
  commandOutcome: 'not-submitted' | 'unknown'
}
export type LocalReviewResponse<T> = { state: 'ready'; data: T } | LocalReviewFailure
export type PreparedLocalReviewCommand = Readonly<{ localCommandId: string }>

/** Dormant transport, not a capability/authorization decision or UI cutover.
 * Create per authenticated membership + session epoch + selected account/review.
 * isCurrent must become false on logout/review/account/epoch change, even A→B→A;
 * dispose the old client. Never persist prepared commands or token in browser storage.
 */
export function createCanonicalLocalReviewsClient(options: {
  scope: CanonicalReviewScope
  actorMembershipId: number
  accessToken: string
  isCurrent: () => boolean
  fetch?: typeof fetch
}) {
  const scope = { ...options.scope }
  const membership = options.actorMembershipId
  const token = options.accessToken
  const current = options.isCurrent
  const fetcher = options.fetch ?? globalThis.fetch
  const pending = new Set<AbortController>()
  const prepared = new WeakMap<PreparedLocalReviewCommand, string>()
  let disposed = false, contextSequence = 0, historySequence = 0
  const active = () => !disposed && current()
  const failure = (state: LocalReviewFailure['state'], submitted = false): LocalReviewFailure => ({
    state, commandOutcome: submitted ? 'unknown' : 'not-submitted',
  })

  async function request<T>(path: string, parse: (value: unknown) => T,
    stillCurrent: () => boolean, body?: string): Promise<LocalReviewResponse<T>> {
    if (!active() || !stillCurrent()) return failure('stale')
    if (!Number.isInteger(membership) || membership < 1 || membership > 2147483647
      || typeof token !== 'string' || !token.trim()) return failure('unauthenticated')
    const controller = new AbortController()
    pending.add(controller)
    const submitted = body !== undefined
    const stale = () => !active() || !stillCurrent()
    try {
      // No shared refresh/retry layer: never replay a mutation implicitly.
      const response = await fetcher(buildApiUrl(path), {
        method: submitted ? 'POST' : 'GET', cache: 'no-store', credentials: 'omit',
        redirect: 'error', signal: controller.signal,
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json',
          ...(submitted ? { 'Content-Type': 'application/json' } : {}) },
        ...(submitted ? { body } : {}),
      })
      if (stale()) return failure('stale', submitted)
      if (!response.ok) {
        // Do not parse, expose or log arbitrary server/provider error text.
        const errors: Partial<Record<number, LocalReviewFailure['state']>> = {
          400: 'invalid-request', 401: 'unauthenticated', 403: 'no-access', 404: 'not-found', 409: 'conflict',
        }
        const state = errors[response.status]
        return failure(state ?? 'unavailable', submitted)
      }
      if (response.status !== 200 || response.headers.get('content-type')?.split(';')[0].trim().toLowerCase()
        !== 'application/json') return failure('invalid-response', submitted)
      let data: T
      try { data = parse(await response.json()) }
      catch { return failure(stale() ? 'stale' : 'invalid-response', submitted) }
      return stale() ? failure('stale', submitted) : { state: 'ready', data }
    } catch {
      return failure(stale() ? 'stale' : 'unavailable', submitted)
    } finally { pending.delete(controller) }
  }

  return {
    dispose() {
      disposed = true
      for (const controller of pending) controller.abort()
      pending.clear()
    },
    async context(review?: { reviewId: string; externalReviewId: string }) {
      const sequence = ++contextSequence
      const expected = review ? { ...review } : undefined
      let path: string
      try { path = buildCanonicalReviewLocalContextPath(scope, expected) }
      catch { return failure('invalid-request') }
      return request(path, value => {
        const data = parseCanonicalReviewLocalContext(value, scope, expected)
        if (data.actorMembershipId !== membership) throw new Error('REVIEW_CONTEXT_ACTOR_MISMATCH')
        return data
      }, () => sequence === contextSequence)
    },
    async history(input: CanonicalReviewHistoryRequest) {
      const sequence = ++historySequence
      const query = { ...input }
      let path: string
      try { path = buildCanonicalReviewHistoryPath(scope, query) }
      catch { return failure('invalid-request') }
      return request(path, value => parseCanonicalReviewHistory(value, scope, query),
        () => sequence === historySequence)
    },
    prepare(command: CanonicalReviewLocalCommand): PreparedLocalReviewCommand {
      if (!active() || command.actorMembershipId !== membership) throw new Error('REVIEW_COMMAND_PREPARATION_DENIED')
      const bytes = encodeCanonicalReviewLocalCommand(command, scope)
      const handle = Object.freeze({ localCommandId: command.localCommandId })
      prepared.set(handle, bytes)
      return handle
    },
    async submit(handle: PreparedLocalReviewCommand) {
      const body = prepared.get(handle)
      if (body === undefined) return failure('invalid-request')
      const command = JSON.parse(body) as CanonicalReviewLocalCommand
      // Explicit retry with this SAME handle sends identical bytes and UUIDs.
      // A 409 requires context reload and a new human decision, never auto-approve.
      return request(canonicalReviewLocalCommandPath,
        value => parseCanonicalReviewLocalResult(value, command), () => true, body)
    },
  }
}
