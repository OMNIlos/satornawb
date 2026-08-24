export const AUTH_STORAGE_KEY = 'ogni.auth.access-token'
export const AUTH_ACCESS_TOKEN_REFRESHED_EVENT = 'ogni:auth-access-token-refreshed'
export const AUTH_ACCESS_TOKEN_CLEARED_EVENT = 'ogni:auth-access-token-cleared'

type NotifyOptions = {
  notify?: boolean
}

let memoryAccessToken: string | null = null

function browserWindow() {
  return typeof window === 'undefined' ? null : window
}

export function readStoredAccessToken() {
  const win = browserWindow()
  return win ? win.localStorage.getItem(AUTH_STORAGE_KEY) : memoryAccessToken
}

export function storeAccessToken(accessToken: string, options: NotifyOptions = {}) {
  const win = browserWindow()
  if (win) {
    win.localStorage.setItem(AUTH_STORAGE_KEY, accessToken)
  } else {
    memoryAccessToken = accessToken
  }
  if (options.notify !== false && win) {
    win.dispatchEvent(new CustomEvent(AUTH_ACCESS_TOKEN_REFRESHED_EVENT, { detail: { accessToken } }))
  }
}

export function clearStoredAccessToken(options: NotifyOptions = {}) {
  const win = browserWindow()
  if (win) {
    win.localStorage.removeItem(AUTH_STORAGE_KEY)
  } else {
    memoryAccessToken = null
  }
  if (options.notify !== false && win) {
    win.dispatchEvent(new CustomEvent(AUTH_ACCESS_TOKEN_CLEARED_EVENT))
  }
}
