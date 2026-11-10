/* src/website.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import chalk from "chalk"
import { serveFile } from "@std/http/file-server"
import { isAbsolute, join, relative } from "@std/path"
import { config, requireClientId } from "./config.ts"
import * as downloads from "./utils/downloads.ts"

export interface StatusSource {
  guildCount(): number
  latency(): number | null
  shards(): Array<{
    id: number
    guilds: number
    latency: number | null
  }>
}

const sitemapSkip = new Set([
  "404.html",
  "meta-example.html",
])

let server: Deno.HttpServer | null = null

export function webAsset(name: string): string | null {
  try {
    const root = Deno.realPathSync(config.webDir)
    const path = Deno.realPathSync(join(root, name))
    const inside = relative(root, path)
    if (inside.startsWith("..") || isAbsolute(inside)) {
      return null
    }
    return Deno.statSync(path).isFile ? path : null
  } catch {
    return null
  }
}

function withStatus(response: Response, status: number): Response {
  return new Response(response.body, {
    status,
    headers: response.headers,
  })
}

function redirect(location: string): Response {
  return new Response(null, {
    status: 301,
    headers: {
      location,
    },
  })
}

function json(payload: unknown): Response {
  return Response.json(payload, {
    headers: {
      "cache-control": "no-store",
    },
  })
}

function plain(body: string, status: number): Response {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/plain; charset=utf-8",
    },
  })
}

async function page(
  request: Request,
  name: string,
  status = 200,
): Promise<Response> {
  const path = webAsset(name)
  if (path === null) {
    return plain(`web/${name} is missing`, 500)
  }
  const response = await serveFile(request, path)
  return status === 200 ? response : withStatus(response, status)
}

async function notFound(request: Request): Promise<Response> {
  const path = webAsset("404.html")
  if (path === null) {
    return plain("404: Not Found", 404)
  }
  return withStatus(await serveFile(request, path), 404)
}

function decoded(part: string): string | null {
  try {
    return decodeURIComponent(part)
  } catch {
    return null
  }
}

function serveDownload(
  request: Request,
  slot: string,
  name: string,
): Promise<Response> {
  if (!downloads.slotPattern.test(slot) || !downloads.validName(name)) {
    return notFound(request)
  }

  const directory = downloads.managedSlot(join(config.downloadsDir, slot))
  if (directory === null) {
    return notFound(request)
  }

  let path: string
  try {
    path = Deno.realPathSync(join(directory, name))
    if (
      relative(directory, path) !== name || !Deno.statSync(path).isFile
    ) {
      return notFound(request)
    }
  } catch {
    return notFound(request)
  }

  // Someone fetching it keeps it alive past the retention sweep
  try {
    const now = new Date()
    Deno.utimeSync(directory, now, now)
    Deno.utimeSync(path, now, now)
  } catch {
    // Serving matters more than the timestamp
  }

  return serveFile(request, path)
}

export function publicPages(): Array<
  [location: string, modified: number]
> {
  let candidates: string[]
  try {
    candidates = [...Deno.readDirSync(config.webDir)]
      .map((entry) => entry.name)
      .sort()
  } catch {
    return []
  }

  const pages: Array<[string, number]> = []
  for (const name of candidates) {
    if (!name.endsWith(".html") || sitemapSkip.has(name)) {
      continue
    }
    try {
      const stat = Deno.statSync(join(config.webDir, name))
      if (!stat.isFile || stat.size === 0) {
        continue
      }
      pages.push([
        name === "index.html" ? "/" : `/${name}`,
        stat.mtime?.getTime() ?? Date.now(),
      ])
    } catch {
      continue
    }
  }
  return pages
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}

export function sitemap(): Response {
  const lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ]

  for (const [location, modified] of publicPages()) {
    const stamp = new Date(modified).toISOString().slice(0, 10)
    lines.push("  <url>")
    lines.push(`    <loc>${escapeXml(config.siteUrl + location)}</loc>`)
    lines.push(`    <lastmod>${stamp}</lastmod>`)
    lines.push("  </url>")
  }

  lines.push("</urlset>")

  return new Response(lines.join("\n") + "\n", {
    headers: {
      "content-type": "application/xml; charset=utf-8",
      "cache-control": "public, max-age=3600",
    },
  })
}

export function robots(): Response {
  const body = [
    "User-agent: *",
    "Allow: /",
    "Disallow: /d/",
    "Disallow: /api/",
    "",
    `Sitemap: ${config.siteUrl}/sitemap.xml`,
    "",
  ].join("\n")

  return new Response(body, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=3600",
    },
  })
}

export function createHandler(
  bot: StatusSource | null = null,
): (request: Request) => Response | Promise<Response> {
  const startedAt = performance.now()

  const status = () => {
    const payload: Record<string, unknown> = {
      version: config.version,
      uptime: Math.floor((performance.now() - startedAt) / 1000),
    }
    if (bot !== null) {
      payload.servers = bot.guildCount()
      const latency = bot.latency()
      if (latency !== null) {
        payload.latency = latency
      }
    }
    return json(payload)
  }

  const shards = () => {
    const list = bot?.shards() ?? []
    return json({
      shardCount: list.length,
      shards: list,
    })
  }

  return (request) => {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return plain("405: Method Not Allowed", 405)
    }

    const path = new URL(request.url).pathname

    switch (path) {
      case "/":
        return page(request, "index.html")
      case "/shards":
        return page(request, "shards.html", 203)
      case "/status":
        return redirect("/shards")
      case "/privacy":
        return page(request, "privacy.html")
      case "/terms":
        return page(request, "terms.html")
      case "/api/status":
        return status()
      case "/api/shards":
        return shards()
      case "/sitemap.xml":
        return sitemap()
      case "/robots.txt":
        return robots()
      case "/docs":
        return redirect("https://docs.doughmination.gay/projects/sandrone")
      case "/support":
        return redirect("https://discord.gg/N8gCjS294R")
      case "/invite":
        try {
          return redirect(
            "https://discord.com/oauth2/authorize?client_id=" +
              requireClientId(),
          )
        } catch (error) {
          return plain(String(error), 500)
        }
    }

    const download = path.match(/^\/d\/([^/]+)\/([^/]+)$/)
    if (download) {
      const slot = decoded(download[1])
      const name = decoded(download[2])
      if (slot === null || name === null) {
        return notFound(request)
      }
      return serveDownload(request, slot, name)
    }

    const asset = decoded(path.slice(1))
    const assetPath = asset === null ? null : webAsset(asset)
    return assetPath === null
      ? notFound(request)
      : serveFile(request, assetPath)
  }
}

export function startServer(bot: StatusSource | null = null): void {
  if (server !== null) {
    return
  }

  Deno.mkdirSync(config.downloadsDir, { recursive: true })
  try {
    server = Deno.serve(
      {
        hostname: config.downloadsHost,
        port: config.downloadsPort,
        onListen() {
          console.log(
            chalk.cyan(
              `[website] serving ${config.webDir} on ` +
                `${config.downloadsHost}:${config.downloadsPort} as ` +
                config.downloadsUrl,
            ),
          )
        },
      },
      createHandler(bot),
    )
  } catch (error) {
    server = null
    console.log(
      chalk.red(
        `[website] could not listen on ${config.downloadsPort}: ${error}`,
      ),
    )
  }
}

export async function stopServer(): Promise<void> {
  if (server !== null) {
    await server.shutdown()
    server = null
  }
}
