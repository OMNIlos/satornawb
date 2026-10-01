import { cp, mkdir, rm } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = resolve(root, 'dist')

await rm(dist, { recursive: true, force: true })
await mkdir(dist, { recursive: true })
await cp(resolve(root, 'manifest.json'), resolve(dist, 'manifest.json'))
await cp(resolve(root, 'README.md'), resolve(dist, 'README.md'))
await cp(resolve(root, 'src'), resolve(dist, 'src'), { recursive: true })

console.log(`Built extension to ${dist}`)
