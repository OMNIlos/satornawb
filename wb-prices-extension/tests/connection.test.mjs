import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
const source = readFileSync(new URL('../src/connection.js', import.meta.url), 'utf8')
function connection(code = source) {
  const context = vm.createContext({ URL })
  vm.runInContext(code, context)
  return context.WbPricesConnection
}

test('custom package defaults never rebind a legacy token to another server', () => {
  const c = connection(source.replace("const DEFAULT_SERVER_URL = 'https://api.elfprint-system.ru'",
    "const DEFAULT_SERVER_URL = 'https://new.example'"))
  assert.equal(c.DEFAULT_SERVER_URL, 'https://new.example')
  assert.equal(c.LEGACY_SERVER_URL, 'https://api.elfprint-system.ru')
})

test('LOCAL artifact cannot connect or request permissions for a remote server', () => {
  const c = connection(source.replace('const ALLOW_LOCAL_SERVER = false', 'const ALLOW_LOCAL_SERVER = true')
    .replace('const LOCAL_ONLY = false', 'const LOCAL_ONLY = true'))
  assert.equal(c.normalizeServerUrl('http://127.0.0.1:58017'), 'http://127.0.0.1:58017')
  for (const url of ['https://api.elfprint-system.ru', 'https://new.example', 'http://remote.example']) {
    assert.throws(() => c.normalizeServerUrl(url), /server_invalid/)
    assert.throws(() => c.permissionOrigin(url), /server_invalid/)
  }
})
