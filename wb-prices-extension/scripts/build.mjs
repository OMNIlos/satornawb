import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// Same dependency-free copy build as the existing Avito extension.
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = resolve(root, 'dist')
await rm(dist, { recursive: true, force: true })
await mkdir(dist, { recursive: true })
await cp(resolve(root, 'manifest.json'), resolve(dist, 'manifest.json'))
await cp(resolve(root, 'README.md'), resolve(dist, 'README.md'))
await cp(resolve(root, 'src'), resolve(dist, 'src'), { recursive: true })
// One MAIN entry avoids Chrome deduplicating a shared filename across worlds.
const main = await Promise.all(['contract.js', 'observer.js'].map((file) => readFile(resolve(root, 'src', file), 'utf8')))
await writeFile(resolve(dist, 'src/page-observer.js'), main.join('\n;\n'))
await rm(resolve(dist, 'src/observer.js'))
const manifest = JSON.parse(await readFile(resolve(dist, 'manifest.json'), 'utf8'))
for (const script of manifest.content_scripts) for (const file of script.js) await readFile(resolve(dist, file))
console.log('Built extension to dist')
