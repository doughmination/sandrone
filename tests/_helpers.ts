/* tests/_helpers.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { join } from "@std/path"
import type { DataBase } from "../src/utils/storage.ts"

// Points a shared database at a fresh temp file for one test
export function isolate(db: DataBase): string {
  const directory = Deno.makeTempDirSync({ prefix: "sandrone-test-" })
  db.path = join(directory, `${db.name}.jp`)
  db.reload()
  return directory
}

// Swaps fields on an object for the length of one test, like monkeypatch
export function patch<T extends object>(
  target: T,
  changes: Partial<T>,
): () => void {
  const previous: Partial<T> = {}
  for (const key of Object.keys(changes) as Array<keyof T>) {
    previous[key] = target[key]
    target[key] = changes[key] as T[keyof T]
  }
  return () => Object.assign(target, previous)
}

export function tempDir(): string {
  return Deno.makeTempDirSync({ prefix: "sandrone-test-" })
}
