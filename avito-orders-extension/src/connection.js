// Shared by the popup and service worker; never infer a server from an Avito page.
globalThis.SatornaConnection = {
  defaultUrl: 'https://app.elfprint-system.ru',
  // Earlier hosted addresses of the same platform: saved settings move to defaultUrl.
  retiredUrls: ['https://ogni-frontend.vercel.app', 'https://satorna-wb.vercel.app'],
  localUrl: 'http://127.0.0.1:5177',
  normalize(value) {
    let url
    try { url = new URL(String(value || '').trim()) } catch {
      throw new Error('Укажите полный адрес Satorna, например http://127.0.0.1:5177')
    }
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    if (url.username || url.password || url.search || url.hash || !/^\/*$/.test(url.pathname)
      || !(url.protocol === 'https:' || (url.protocol === 'http:' && loopback))) {
      throw new Error('Нужен адрес без пути и пароля: HTTPS либо HTTP на localhost/127.0.0.1')
    }
    return this.retiredUrls.includes(url.origin) ? this.defaultUrl : url.origin
  },
  async read() {
    const legacy = await chrome.storage.sync.get({ backendUrl: this.defaultUrl, accessToken: '' })
    const local = await chrome.storage.local.get({ connection: null })
    return local.connection || legacy
  },
  async save(backendUrl, accessToken) {
    const connection = { backendUrl: this.normalize(backendUrl), accessToken: String(accessToken || '').trim() }
    // Connection credentials belong to this computer, not Chrome cloud sync.
    await chrome.storage.local.set({ connection })
    await chrome.storage.sync.remove(['backendUrl', 'accessToken'])
    return connection
  },
}
