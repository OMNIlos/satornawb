'use strict'
globalThis.WbPricesConnection = (() => {
  const DEFAULT_SERVER_URL = 'https://api.elfprint-system.ru'
  const LEGACY_SERVER_URL = 'https://api.elfprint-system.ru'
  const ALLOW_LOCAL_SERVER = false
  const LOCAL_ONLY = false
  function normalizeServerUrl(value) {
    if (typeof value !== 'string' || value.length > 2048) throw new Error('server_invalid')
    let url
    try { url = new URL(value.trim()) } catch { throw new Error('server_invalid') }
    const local = ALLOW_LOCAL_SERVER && url.protocol === 'http:'
      && ['127.0.0.1', 'localhost'].includes(url.hostname)
    if ((LOCAL_ONLY && !local) || (!local && url.protocol !== 'https:') || url.username || url.password
        || url.pathname !== '/' || url.search || url.hash) throw new Error('server_invalid')
    return url.origin
  }
  return Object.freeze({ DEFAULT_SERVER_URL, LEGACY_SERVER_URL, normalizeServerUrl,
    permissionOrigin: origin => `${normalizeServerUrl(origin)}/*` })
})()
