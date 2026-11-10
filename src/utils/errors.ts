/* src/utils/errors.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import chalk from "chalk"
import {
  DiscordAPIError,
  HTTPError,
  type Interaction,
  RateLimitError,
} from "discord.js"
import { JPError } from "jpcl-lang"
import { createHash } from "node:crypto"
import { basename } from "@std/path"
import { qualifiedName } from "../framework.ts"
import {
  BotMissingPermissions,
  CommandOnCooldown,
  MissingPermissions,
  NotFoundError,
  toError,
  UpstreamError,
} from "./failures.ts"
import { database } from "./storage.ts"

export const db = database("errors", { version: 1 })

export const recentKey = "recent"
export const keepLimit = 50
export const textLimit = 400
export const traceLimit = 2400

// Crockford's alphabet: no I, L, O or U, so a retyped code still matches
export const refAlphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
export const refLength = 4

export const fallbackCode = "MALFUNCTION"
export const loneWorkCode = "PUPPET"

const fileErrors = [
  Deno.errors.NotFound,
  Deno.errors.PermissionDenied,
  Deno.errors.AlreadyExists,
  Deno.errors.IsADirectory,
  Deno.errors.NotADirectory,
  Deno.errors.WriteZero,
  Deno.errors.UnexpectedEof,
  Deno.errors.Busy,
  Deno.errors.FilesystemLoop,
]

const networkErrors = [
  Deno.errors.ConnectionRefused,
  Deno.errors.ConnectionReset,
  Deno.errors.ConnectionAborted,
  Deno.errors.NotConnected,
  Deno.errors.TimedOut,
  Deno.errors.AddrNotAvailable,
  Deno.errors.NetworkUnreachable,
]

function discordStatus(error: Error): number | null {
  return error instanceof DiscordAPIError ? error.status : null
}

// fetch() reports a dead connection as a bare TypeError
function isNetworkFailure(error: Error): boolean {
  if (error.name === "TimeoutError" || error.name === "AbortError") {
    return true
  }
  if (networkErrors.some((kind) => error instanceof kind)) {
    return true
  }
  return error instanceof TypeError &&
    /fetch|network|error sending request|dns/i.test(error.message)
}

type Matcher = (error: Error) => boolean

// Tested in order, so the narrow Discord statuses come before the broad ones
export const codes: ReadonlyArray<readonly [string, string, Matcher]> = [
  [
    "WORKSHOP",
    "She is not allowed to do that here — a permission is missing.",
    (error) =>
      error instanceof BotMissingPermissions ||
      error instanceof MissingPermissions ||
      discordStatus(error) === 403,
  ],
  [
    "VANISHED",
    "What was asked for is not there — a user, channel, role or page.",
    (error) =>
      error instanceof NotFoundError ||
      discordStatus(error) === 404,
  ],
  [
    "OVERLOAD",
    "Too much, too fast — a cooldown or a rate limit.",
    (error) =>
      error instanceof CommandOnCooldown ||
      error instanceof RateLimitError ||
      discordStatus(error) === 429,
  ],
  [
    "STRINGS",
    "Discord itself refused or dropped the connection.",
    (error) =>
      error instanceof DiscordAPIError ||
      error instanceof HTTPError,
  ],
  [
    "BLIZZARD",
    "Somewhere outside Discord did not answer — an API or the network.",
    (error) =>
      error instanceof UpstreamError ||
      isNetworkFailure(error),
  ],
  [
    "FOUNDRY",
    "Storage went wrong — a file, a path, or the .jp databases.",
    (error) =>
      error instanceof JPError ||
      fileErrors.some((kind) => error instanceof kind),
  ],
  [
    "BLUEPRINT",
    "The data was the wrong shape — bad JSON, a missing key, a bad value.",
    (error) =>
      error instanceof SyntaxError ||
      error instanceof TypeError ||
      error instanceof RangeError ||
      error instanceof ReferenceError,
  ],
]

export const codeMeanings: Record<string, string> = {
  ...Object.fromEntries(codes.map(([name, meaning]) => [name, meaning])),
  [loneWorkCode]: "The puppet broke on its own, away from any command.",
  [fallbackCode]: "Nothing she recognises. Read the traceback.",
}

export interface Entry {
  ref: string
  code: string
  when: number
  first: number
  count: number
  source: string
  command: string
  kind: string
  text: string
  guild: string
  channel: string
  user: string
  missing: string[]
  trace: string
}

const longNumbers = /\d{2,}/g

interface Labelled {
  id?: string
  name?: string | null
  username?: string
}

export function label(target: unknown): string {
  if (target === null || target === undefined) {
    return "—"
  }
  const labelled = target as Labelled
  const name = labelled.name ?? labelled.username ?? String(target)
  return labelled.id ? `${name} (${labelled.id})` : String(name)
}

export function kindOf(error: Error): string {
  if (error instanceof DiscordAPIError) {
    return "DiscordAPIError"
  }
  return error.name || error.constructor.name || "Error"
}

export function traceOf(error: Error): string {
  return (error.stack ?? "").trim().slice(-traceLimit)
}

export function missingOf(error: Error): string[] {
  const missing = (error as { missingPermissions?: unknown })
    .missingPermissions
  return Array.isArray(missing) ? missing.map(String) : []
}

// The innermost frame of the stack, as "file.ts:42"
export function frameOf(error: Error): string {
  const lines = (error.stack ?? "").split("\n").slice(1)
  for (const line of lines) {
    const found = line.match(/([^\s(]+):(\d+):\d+\)?\s*$/)
    if (found) {
      return `${basename(found[1])}:${found[2]}`
    }
  }
  return ""
}

export function codeOf(error: Error, source = ""): string {
  for (const [name, , matches] of codes) {
    if (matches(error)) {
      return name
    }
  }
  return source.endsWith("command") ? fallbackCode : loneWorkCode
}

// Ids are blanked out so one fault hit by many people keeps one code
export function digestOf(error: Error, command?: string | null): string {
  const seed = [
    kindOf(error),
    command ?? "",
    error.message.replace(longNumbers, "#"),
    frameOf(error),
  ].join("|")

  const bytes = createHash("sha256").update(seed, "utf8").digest()
  let value = new DataView(bytes.buffer, bytes.byteOffset, 8)
    .getBigUint64(0)

  const base = BigInt(refAlphabet.length)
  const characters: string[] = []
  for (let index = 0; index < refLength; index++) {
    characters.push(refAlphabet[Number(value % base)])
    value /= base
  }
  return characters.reverse().join("")
}

export function reference(
  error: Error,
  command?: string | null,
  source = "",
): string {
  return `${codeOf(error, source)}-${digestOf(error, command)}`
}

function isEntry(value: unknown): value is Entry {
  return typeof value === "object" && value !== null &&
    !Array.isArray(value)
}

export function entries(): Entry[] {
  return db.key(recentKey).list().filter(isEntry)
}

export function recent(limit = 10): Entry[] {
  return entries().slice(0, limit)
}

export function count(): number {
  return entries().length
}

// Accepts `workshop-4f2k`, #WORKSHOP–4F2K, spaced out, and so on
export function tidyRef(ref: string): string {
  const cleaned = ref
    .trim()
    .replace(/^`+|`+$/g, "")
    .replace(/^#+/, "")
    .toUpperCase()
    .replace(/[\s_–—]+/g, "-")
    .replace(/-+/g, "-")
  return cleaned.replace(/^-+|-+$/g, "")
}

export function find(ref: string): Entry | null {
  const wanted = tidyRef(ref)
  if (!wanted) {
    return null
  }

  const stored = entries()
  for (const entry of stored) {
    if (String(entry.ref ?? "").toUpperCase() === wanted) {
      return entry
    }
  }

  // Someone quoted only half of it: the digest alone, or just the code
  for (const entry of stored) {
    const [code, digest] = String(entry.ref ?? "").toUpperCase().split("-")
    if (wanted === digest || wanted === code) {
      return entry
    }
  }
  return null
}

export function byCode(code: string): Entry[] {
  const wanted = tidyRef(code)
  return entries().filter(
    (entry) => String(entry.code ?? "").toUpperCase() === wanted,
  )
}

// The line added to the reply sent to whoever hit the error
export function note(entry: Entry | null | undefined): string {
  if (!entry?.ref) {
    return ""
  }
  return `\n-# Fault \`${entry.ref}\` — quote that if you report this.`
}

export function clear(): number {
  const total = count()
  if (total) {
    db.key(recentKey).delete().save()
  }
  return total
}

export interface RecordOptions {
  source: string
  command?: string | null
  guild?: unknown
  channel?: unknown
  user?: unknown
}

// Called from error handlers, so it never throws a second error
export function record(
  thrown: unknown,
  options: RecordOptions,
): Entry | null {
  const error = toError(thrown)
  try {
    const code = codeOf(error, options.source)
    const ref = `${code}-${digestOf(error, options.command)}`
    const now = Math.floor(Date.now() / 1000)
    const seen = find(ref)

    const entry: Entry = {
      ref,
      code,
      when: now,
      first: seen ? Number(seen.first ?? now) : now,
      count: seen ? Number(seen.count ?? 1) + 1 : 1,
      source: options.source,
      command: options.command || "—",
      kind: kindOf(error),
      text: (error.message || String(error)).slice(0, textLimit),
      guild: label(options.guild),
      channel: label(options.channel),
      user: label(options.user),
      missing: missingOf(error),
      trace: traceOf(error),
    }

    const others = entries().filter((other) => other.ref !== ref)
    db.key(recentKey)
      .write([
        entry,
        ...others.slice(0, keepLimit - 1),
      ])
      .save()
    return entry
  } catch (failure) {
    console.log(
      chalk.red(`[errors] could not record ${kindOf(error)}: ${failure}`),
    )
    return null
  }
}

export function fromInteraction(
  interaction: Interaction,
  error: unknown,
): Entry | null {
  return record(error, {
    source: "slash command",
    command: qualifiedName(interaction),
    guild: interaction.guild,
    channel: interaction.channel,
    user: interaction.user,
  })
}
