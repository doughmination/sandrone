/* src/config.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { walkSync } from "@std/fs/walk"
import { fromFileUrl, join, relative, resolve, SEPARATOR } from "@std/path"
import denoJson from "../deno.json" with { type: "json" }

const repoRoot = resolve(fromFileUrl(new URL("../", import.meta.url)))
const sourceDir = join(repoRoot, "src")

// Blank and whitespace-only values count as unset
function envValue(name: string): string | undefined {
  const value = Deno.env.get(name)?.trim()
  return value ? value : undefined
}

function envNumber(name: string, fallback: number): number {
  const value = envValue(name)
  const parsed = value === undefined ? NaN : Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const downloadsPort = envNumber("DOWNLOADS_PORT", 2020)
const downloadsUrl = (
  envValue("DOWNLOADS_URL") ?? `http://localhost:${downloadsPort}`
).replace(/\/+$/, "")

export const config = {
  repoRoot,
  sourceDir,
  commandsDir: join(sourceDir, "commands"),
  cogsDir: join(sourceDir, "commands", "cogs"),
  settingsDir: join(sourceDir, "commands", "settings"),
  webDir: join(repoRoot, "web"),
  assetsDir: join(repoRoot, "web", "assets"),
  dataDir: join(repoRoot, "data"),
  cogStatePath: join(repoRoot, "cog_state.json"),

  version: denoJson.version ?? "unknown",

  token: envValue("BOT_TOKEN"),
  clientId: envValue("CLIENT_ID"),
  devMode: envValue("DEV_MODE")?.toLowerCase() === "true",
  githubToken: envValue("GITHUB_TOKEN"),

  downloadsDir: envValue("DOWNLOADS_DIR") ?? join(repoRoot, "downloads"),
  downloadsHost: envValue("DOWNLOADS_HOST") ?? "0.0.0.0",
  downloadsPort,
  downloadsUrl,
  siteUrl: (envValue("SITE_URL") ?? downloadsUrl).replace(/\/+$/, ""),
  downloadsRetentionHours: envNumber("DOWNLOADS_RETENTION_HOURS", 24),
  downloadsMaxSize: envNumber("DOWNLOADS_MAX_SIZE_MIB", 2048) * 1024 *
    1024,

  displayNameFont: 16 as number | null,
  displayNameEffect: 7 as number | null,
  displayNameColors: [
    0xD52D00,
    0xFF9A56,
    0xFFFFFF,
    0xD362A4,
    0xA30262,
  ] as number[] | null,

  owners: [
    "1464890289922641993",
    "1025770042245251122",
  ],
}

export function requireToken(): string {
  if (!config.token) {
    throw new Error(
      "BOT_TOKEN is not set. Add it to your .env file before starting " +
        "the bot.",
    )
  }
  return config.token
}

export function requireClientId(): string {
  if (!config.clientId) {
    throw new Error(
      "CLIENT_ID is not set. Add it to your .env before starting the bot.",
    )
  }
  return config.clientId
}

export function requireGithubToken(): string {
  if (!config.githubToken) {
    throw new Error(
      "GITHUB_TOKEN is not set. Add it to your .env file to use /github.",
    )
  }
  return config.githubToken
}

// Test files and _private helpers sitting beside cogs are not cogs
function isModuleFile(name: string): boolean {
  return name.endsWith(".ts") &&
    !name.endsWith("_test.ts") &&
    !name.startsWith("_")
}

// "fun/judge.ts" becomes the handle "fun.judge", same as the Python bot
export function discoverCogHandles(
  directory: string = config.cogsDir,
): string[] {
  const handles: string[] = []
  try {
    for (const entry of walkSync(directory, { includeDirs: false })) {
      if (!isModuleFile(entry.name)) {
        continue
      }
      const withoutSuffix = relative(directory, entry.path).slice(0, -3)
      handles.push(withoutSuffix.split(SEPARATOR).join("."))
    }
  } catch (error) {
    if (!(error instanceof Deno.errors.NotFound)) {
      throw error
    }
  }
  return handles.sort()
}

// Top-level modules in one folder only, e.g. src/commands/*.ts
export function discoverModules(
  directory: string,
  prefix: string,
): string[] {
  const names: string[] = []
  try {
    for (const entry of Deno.readDirSync(directory)) {
      if (entry.isFile && isModuleFile(entry.name)) {
        names.push(`${prefix}.${entry.name.slice(0, -3)}`)
      }
    }
  } catch (error) {
    if (!(error instanceof Deno.errors.NotFound)) {
      throw error
    }
  }
  return names.sort()
}

export function loadDisabled(): Set<string> {
  try {
    const data = JSON.parse(Deno.readTextFileSync(config.cogStatePath))
    const disabled = Array.isArray(data?.disabled) ? data.disabled : []
    return new Set(disabled.map(String))
  } catch {
    return new Set()
  }
}

export function saveDisabled(disabled: Set<string>): void {
  const body = {
    disabled: [...disabled].sort(),
  }
  Deno.writeTextFileSync(
    config.cogStatePath,
    JSON.stringify(body, null, 2) + "\n",
  )
}

export function setDisabled(name: string, disabled: boolean): void {
  const current = loadDisabled()
  if (disabled) {
    current.add(name)
  } else {
    current.delete(name)
  }
  saveDisabled(current)
}
