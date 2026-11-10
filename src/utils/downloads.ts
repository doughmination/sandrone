/* src/utils/downloads.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import chalk from "chalk"
import { encodeBase64Url } from "@std/encoding/base64url"
import { basename, dirname, join } from "@std/path"
import { config } from "../config.ts"
import type { Timer } from "../framework.ts"

export const sweepInterval = 3_600_000

export const slotPattern = /^[A-Za-z0-9_-]{1,64}$/
export const metaName = ".meta.json"
export const markerName = ".sandrone-download"

// deno-lint-ignore no-explicit-any
export type Meta = Record<string, any>

export interface CachedDownload extends Meta {
  key: string
  name: string
  title: string
  size: number
  slot: string
}

function isFile(path: string): boolean {
  try {
    return Deno.statSync(path).isFile
  } catch {
    return false
  }
}

function isDirectory(path: string): boolean {
  try {
    return Deno.statSync(path).isDirectory
  } catch {
    return false
  }
}

function touch(path: string): void {
  const now = new Date()
  Deno.utimeSync(path, now, now)
}

// Same as Python's secrets.token_urlsafe(9): 12 URL-safe characters
function slotName(): string {
  return encodeBase64Url(crypto.getRandomValues(new Uint8Array(9)))
}

export function newSlot(): string {
  const directory = join(config.downloadsDir, slotName())
  Deno.mkdirSync(directory, { recursive: true })
  Deno.writeFileSync(join(directory, markerName), new Uint8Array())
  return directory
}

export function managedSlot(slot: string): string | null {
  let root: string
  let resolved: string
  try {
    root = Deno.realPathSync(config.downloadsDir)
    resolved = Deno.realPathSync(slot)
  } catch {
    return null
  }
  if (
    dirname(resolved) !== root || !slotPattern.test(basename(resolved))
  ) {
    return null
  }
  if (
    !isFile(join(resolved, markerName)) &&
    !isFile(join(resolved, metaName))
  ) {
    return null
  }
  return resolved
}

export function discard(slot: string): void {
  const managed = managedSlot(slot)
  if (managed !== null) {
    try {
      Deno.removeSync(managed, { recursive: true })
    } catch {
      // Already gone is as good as removed
    }
  }
}

export function publicUrl(slot: string, name: string): string {
  return `${config.downloadsUrl}/d/${basename(slot)}/${
    encodeURIComponent(name)
  }`
}

export function validName(name: unknown): name is string {
  if (typeof name !== "string" || !name) {
    return false
  }
  if (name === "." || name === ".." || name.startsWith(".")) {
    return false
  }
  if ([...name].some((character) => character.charCodeAt(0) < 32)) {
    return false
  }
  return !name.includes("/") && !name.includes("\\")
}

export function recordSource(
  slot: string,
  key: string,
  name: string,
  extra: Meta,
): void {
  const managed = managedSlot(slot)
  if (managed === null || !validName(name)) {
    throw new RangeError("Invalid download slot or filename")
  }
  const data = {
    ...extra,
    key,
    name,
  }
  Deno.writeTextFileSync(
    join(managed, metaName),
    JSON.stringify(data) + "\n",
  )
}

function managedSlots(): string[] {
  if (!isDirectory(config.downloadsDir)) {
    return []
  }
  const slots: string[] = []
  for (const entry of Deno.readDirSync(config.downloadsDir)) {
    const managed = managedSlot(join(config.downloadsDir, entry.name))
    if (managed !== null) {
      slots.push(managed)
    }
  }
  return slots
}

function retentionCutoff(): number {
  return Date.now() - config.downloadsRetentionHours * 3_600_000
}

function modifiedAt(path: string): number {
  return Deno.statSync(path).mtime?.getTime() ?? 0
}

function isValidMeta(meta: unknown, key: string): meta is Meta {
  if (typeof meta !== "object" || meta === null || Array.isArray(meta)) {
    return false
  }
  const record = meta as Meta
  return record.key === key &&
    validName(record.name) &&
    typeof record.title === "string" &&
    record.title.trim() !== "" &&
    Number.isInteger(record.size) &&
    record.size >= 0
}

export function findCached(key: string): CachedDownload | null {
  const cutoff = retentionCutoff()

  for (const slot of managedSlots()) {
    let meta: unknown
    try {
      meta = JSON.parse(Deno.readTextFileSync(join(slot, metaName)))
    } catch {
      continue
    }
    if (!isValidMeta(meta, key)) {
      continue
    }

    const target = join(slot, meta.name)
    try {
      if (!isFile(target) || modifiedAt(slot) < cutoff) {
        continue
      }
      touch(slot)
      touch(target)
    } catch {
      continue
    }

    return {
      ...meta,
      slot,
    } as CachedDownload
  }

  return null
}

export function purgeExpired(): number {
  const cutoff = retentionCutoff()
  let removed = 0

  for (const slot of managedSlots()) {
    try {
      if (modifiedAt(slot) >= cutoff) {
        continue
      }
      Deno.removeSync(slot, { recursive: true })
      removed += 1
    } catch (error) {
      console.log(
        chalk.red(
          `[downloads] could not remove ${basename(slot)}: ${error}`,
        ),
      )
    }
  }
  return removed
}

function sweepOnce(): void {
  const removed = purgeExpired()
  if (removed) {
    console.log(
      chalk.gray(`[downloads] removed ${removed} expired download(s)`),
    )
  }
}

export function sweepForever(): Timer {
  sweepOnce()
  return setInterval(sweepOnce, sweepInterval)
}
