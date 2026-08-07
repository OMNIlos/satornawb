import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const html = await readFile(new URL('../src/popup.html', import.meta.url), 'utf8')
const js = await readFile(new URL('../src/popup.js', import.meta.url), 'utf8')

function section(id) {
  const match = html.match(new RegExp(`<section[^>]+id="${id}"[\\s\\S]*?<\\/section>`))
  return match?.[0] || ''
}

test('popup opens on a focused collect screen', () => {
  assert.match(html, /data-screen="collect"/)
  assert.match(section('collectScreen'), /Собрать заказы/)
  assert.doesNotMatch(section('collectScreen'), /accessToken/)
  assert.doesNotMatch(section('collectScreen'), /logsList/)
})

test('token and logs live in settings diagnostics, not on the main screen', () => {
  assert.match(section('connectionSettings'), /id="accessToken"/)
  assert.match(section('diagnosticsSettings'), /id="logsList"/)
  assert.match(section('diagnosticsSettings'), /id="clearLogsBtn"/)
})

test('popup script switches between collect and settings screens', () => {
  assert.match(js, /setActiveScreen/)
  assert.match(js, /settingsTab/)
  assert.match(js, /collectTab/)
})
