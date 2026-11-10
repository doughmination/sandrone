/* src/utils/storage.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import chalk from "chalk"
import { JPConfig, JPError, SUFFIX } from "jpcl-lang"
import { dirname, join } from "@std/path"
import { config } from "../config.ts"
import type { Timer } from "../framework.ts"

export const flushInterval = 30_000
export const versionKey = "version"

// deno-lint-ignore no-explicit-any
type Data = Record<string, any>

const databaseRegistry = new Map<string, DataBase>()

function isPlainObject(value: unknown): value is Data {
  return typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
}

function isInteger(value: unknown): value is number | bigint {
  return typeof value === "bigint" ||
    (typeof value === "number" && Number.isInteger(value))
}

// Snowflakes go back to disk as bare integers, like the Python bot wrote
export function storedId(id: string | number | bigint): bigint {
  return BigInt(id)
}

function asIds(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  const ids: string[] = []
  for (const item of value) {
    try {
      ids.push(BigInt(item).toString())
    } catch {
      continue
    }
  }
  return ids
}

// Lists of plain integers stay sorted so diffs of the file stay small
function ordered(items: unknown[]): unknown[] {
  if (!items.every(isInteger)) {
    return items
  }
  return [...items].sort((left, right) => {
    const difference = BigInt(left) - BigInt(right)
    return difference < 0n ? -1 : difference > 0n ? 1 : 0
  })
}

export class Field {
  constructor(
    readonly scope: Scope,
    readonly name: string,
  ) {}

  toString(): string {
    return `<Field ${this.scope.db.name}:${this.scope.label}.${this.name}>`
  }

  read<T = unknown>(fallback?: T): T | undefined {
    const value = this.scope.data()[this.name]
    return value === null || value === undefined ? fallback : value
  }

  list(): unknown[] {
    const value = this.scope.data()[this.name]
    return Array.isArray(value) ? [...value] : []
  }

  ids(): string[] {
    return asIds(this.scope.data()[this.name])
  }

  int(fallback?: number): number | undefined {
    const value = this.scope.data()[this.name]
    if (value === null || value === undefined) {
      return fallback
    }
    const parsed = Number(value)
    return Number.isInteger(parsed) ? parsed : fallback
  }

  has(item: unknown): boolean {
    return this.list().includes(item)
  }

  hasId(id: string): boolean {
    return this.ids().includes(BigInt(id).toString())
  }

  exists(): boolean {
    return this.name in this.scope.data()
  }

  write(value: unknown): this {
    this.scope.data({ create: true })[this.name] = value
    this.scope.db.touch()
    return this
  }

  delete(): this {
    const data = this.scope.data()
    if (this.name in data) {
      delete data[this.name]
      this.scope.db.touch()
    }
    return this
  }

  add(...items: unknown[]): this {
    const current = this.list()
    const fresh = items.filter((item) => !current.includes(item))
    return fresh.length
      ? this.write(ordered([...current, ...fresh]))
      : this
  }

  remove(...items: unknown[]): this {
    return this.removeWhere((item) => items.includes(item))
  }

  toggle(item: unknown): this {
    return this.has(item) ? this.remove(item) : this.add(item)
  }

  addIds(...ids: string[]): this {
    const current = this.list()
    const known = new Set(asIds(current))
    const fresh = ids
      .filter((id) => !known.has(BigInt(id).toString()))
      .map(storedId)
    return fresh.length
      ? this.write(ordered([...current, ...fresh]))
      : this
  }

  removeIds(...ids: string[]): this {
    const unwanted = new Set(ids.map((id) => BigInt(id).toString()))
    return this.removeWhere((item) => {
      const [id] = asIds([item])
      return id !== undefined && unwanted.has(id)
    })
  }

  save(): this {
    this.scope.db.save()
    return this
  }

  // An emptied list is dropped entirely, like the Python prune=True
  private removeWhere(unwanted: (item: unknown) => boolean): this {
    const current = this.list()
    const kept = current.filter((item) => !unwanted(item))
    if (kept.length === current.length) {
      return this
    }
    return kept.length ? this.write(kept) : this.delete()
  }
}

export class Scope {
  constructor(
    readonly db: DataBase,
    readonly name: string | null,
  ) {}

  get label(): string {
    return this.name ?? "<root>"
  }

  toString(): string {
    return `<Scope ${this.db.name}:${this.label}>`
  }

  key(name: string): Field {
    return new Field(this, name)
  }

  data(options: { create?: boolean } = {}): Data {
    const document = this.db.open()
    if (this.name === null) {
      return document.data
    }
    if (options.create) {
      if (!isPlainObject(document.get(this.name))) {
        document.set(this.name, {})
      }
      return document.get(this.name)
    }
    const existing = document.get(this.name)
    return isPlainObject(existing) ? existing : {}
  }

  exists(): boolean {
    return this.name === null || this.db.open().has(this.name)
  }

  keys(): string[] {
    return Object.keys(this.data())
  }

  toObject(): Data {
    return { ...this.data() }
  }

  merge(values: Data): this {
    Object.assign(this.data({ create: true }), values)
    this.db.touch()
    return this
  }

  clear(): this {
    const document = this.db.open()
    if (this.name !== null && document.has(this.name)) {
      document.delete(this.name)
      this.db.touch()
    }
    return this
  }

  save(): this {
    this.db.save()
    return this
  }
}

export class DataBase {
  path: string
  private document: JPConfig | null = null
  private isDirty = false

  constructor(
    readonly name: string,
    readonly version: number | null = null,
  ) {
    this.path = join(config.dataDir, `${name}${SUFFIX}`)
  }

  toString(): string {
    return `<DataBase ${this.name} (${this.isDirty ? "dirty" : "clean"})>`
  }

  open(): JPConfig {
    if (this.document === null) {
      try {
        this.document = JPConfig.loadSync(this.path, { missingOk: true })
      } catch (error) {
        console.log(
          chalk.red(`[database] could not read ${this.path}: ${error}`),
        )
        this.document = new JPConfig(null, { path: this.path })
      }
    }
    return this.document
  }

  has(name: string | bigint): boolean {
    return this.open().has(String(name))
  }

  guild(guildId: string | bigint): Scope {
    return new Scope(this, String(guildId))
  }

  section(name: string | bigint): Scope {
    return new Scope(this, String(name))
  }

  root(): Scope {
    return new Scope(this, null)
  }

  key(name: string): Field {
    return this.root().key(name)
  }

  sections(): string[] {
    return [...this.open().keys()].filter((name) => name !== versionKey)
  }

  toObject(): Data {
    return this.open().toObject({ deep: true })
  }

  get dirty(): boolean {
    return this.isDirty
  }

  touch(): this {
    this.isDirty = true
    return this
  }

  save(options: { force?: boolean } = {}): this {
    if (this.document === null || !(this.isDirty || options.force)) {
      return this
    }

    const document = this.document
    if (
      this.version !== null && document.get(versionKey) !== this.version
    ) {
      document.set(versionKey, this.version)
    }

    this.isDirty = false
    try {
      Deno.mkdirSync(dirname(this.path), { recursive: true })
      document.saveSync(this.path)
    } catch (error) {
      this.isDirty = true
      if (!(error instanceof JPError || error instanceof Error)) {
        throw error
      }
      console.log(
        chalk.red(`[database] could not write ${this.path}: ${error}`),
      )
    }
    return this
  }

  reload(): this {
    this.document = null
    this.isDirty = false
    this.open()
    return this
  }
}

export function database(
  name: string,
  options: { version?: number } = {},
): DataBase {
  const path = join(config.dataDir, `${name}${SUFFIX}`)
  let existing = databaseRegistry.get(path)
  if (existing === undefined) {
    existing = new DataBase(name, options.version ?? null)
    databaseRegistry.set(path, existing)
  }
  return existing
}

export function databases(): DataBase[] {
  return [...databaseRegistry.values()]
}

export function saveAll(): string[] {
  const saved: string[] = []
  for (const db of databaseRegistry.values()) {
    if (db.dirty) {
      db.save()
      saved.push(db.name)
    }
  }
  return saved
}

export function flushForever(interval: number = flushInterval): Timer {
  return setInterval(saveAll, interval)
}
