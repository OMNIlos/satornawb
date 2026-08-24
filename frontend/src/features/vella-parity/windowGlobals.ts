export function clearVellaWindowProperty(target: object, key: PropertyKey) {
  try {
    delete (target as Record<PropertyKey, unknown>)[key]
  } catch {
    // Legacy HTML declares some window functions as non-configurable.
    // React effect cleanup must stay best-effort so StrictMode remounts do not crash the island.
  }
}
