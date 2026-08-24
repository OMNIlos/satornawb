import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import YAML from 'yaml'

const projectRoot = resolve(import.meta.dirname, '../..')
const openApiPath = resolve(projectRoot, 'contracts/openapi/v1.yaml')
const document = YAML.parse(readFileSync(openApiPath, 'utf8'))

const errors = []
const servers = Array.isArray(document.servers) ? document.servers : []
const paths = document.paths && typeof document.paths === 'object' ? Object.keys(document.paths) : []

if (document.openapi !== '3.1.0') {
  errors.push(`Expected OpenAPI 3.1.0, got ${document.openapi}`)
}

if (servers.length !== 1 || servers[0]?.url !== '/') {
  errors.push('Expected a single root server "/" because paths already include /api/v1')
}

for (const path of paths) {
  if (!path.startsWith('/api/v1/')) {
    errors.push(`Path must include /api/v1 prefix: ${path}`)
  }
  if (path.startsWith('/api/v1/api/v1/')) {
    errors.push(`Path has duplicated /api/v1 prefix: ${path}`)
  }
}

if (errors.length > 0) {
  console.error(errors.join('\n'))
  process.exit(1)
}

console.log(`OpenAPI smoke passed: ${paths.length} paths, server ${servers[0].url}`)
