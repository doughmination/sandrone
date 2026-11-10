/* tests/website_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assert, assertEquals, assertStringIncludes } from "@std/assert"
import { basename, join } from "@std/path"
import { config } from "../src/config.ts"
import * as downloads from "../src/utils/downloads.ts"
import * as website from "../src/website.ts"
import { patch, tempDir } from "./_helpers.ts"

function get(
  handler: ReturnType<typeof website.createHandler>,
  path: string,
): Promise<Response> {
  return Promise.resolve(handler(new Request(`http://localhost${path}`)))
}

// A fresh web folder per test, with a fixed public URL
function withWebRoot(test: (root: string) => Promise<void> | void) {
  return async () => {
    const root = tempDir()
    const restore = patch(config, {
      webDir: root,
      siteUrl: "https://sandrone.example",
    })
    try {
      await test(root)
    } finally {
      restore()
    }
  }
}

const fakeBot: website.StatusSource = {
  guildCount: () => 2,
  latency: () => 42,
  shards: () => [
    {
      id: 0,
      guilds: 2,
      latency: 42,
    },
  ],
}

Deno.test(
  "web asset serves only files inside the web directory",
  withWebRoot((root) => {
    const index = join(root, "index.html")
    Deno.writeTextFileSync(index, "Sandrone")
    Deno.writeTextFileSync(join(root, "..", "secret.txt"), "not public")

    assertEquals(website.webAsset("index.html"), Deno.realPathSync(index))
    assertEquals(website.webAsset("../secret.txt"), null)
    assertEquals(website.webAsset("missing.html"), null)
  }),
)

Deno.test(
  "the index page is served at the root",
  withWebRoot(async (root) => {
    Deno.writeTextFileSync(join(root, "index.html"), "Sandrone")
    const response = await get(website.createHandler(), "/")

    assertEquals(response.status, 200)
    assertEquals(await response.text(), "Sandrone")
  }),
)

Deno.test(
  "unknown paths get the 404 page with a 404 status",
  withWebRoot(async (root) => {
    Deno.writeTextFileSync(join(root, "404.html"), "Lost")
    const response = await get(website.createHandler(), "/nowhere")

    assertEquals(response.status, 404)
    assertEquals(await response.text(), "Lost")
  }),
)

Deno.test("status reports the bot when one is attached", async () => {
  const response = await get(website.createHandler(fakeBot), "/api/status")
  const payload = await response.json()

  assertEquals(payload.servers, 2)
  assertEquals(payload.latency, 42)
  assertEquals(payload.version, config.version)
  assert(payload.uptime >= 0)
  assertEquals(response.headers.get("cache-control"), "no-store")
})

Deno.test("status omits bot details when there is no bot", async () => {
  const response = await get(website.createHandler(), "/api/status")
  const payload = await response.json()

  assertEquals("servers" in payload, false)
  assertEquals("latency" in payload, false)
})

Deno.test("shards lists every shard the bot reports", async () => {
  const response = await get(website.createHandler(fakeBot), "/api/shards")

  assertEquals(await response.json(), {
    shardCount: 1,
    shards: [{ id: 0, guilds: 2, latency: 42 }],
  })
})

Deno.test(
  "sitemap lists real pages and skips the ones that should not be",
  withWebRoot(async (root) => {
    Deno.writeTextFileSync(join(root, "index.html"), "Sandrone")
    Deno.writeTextFileSync(join(root, "privacy.html"), "Privacy")
    Deno.writeTextFileSync(join(root, "404.html"), "Not found")
    Deno.writeTextFileSync(join(root, "meta-example.html"), "Example")
    Deno.writeTextFileSync(join(root, "style.css"), "body{}")
    Deno.writeTextFileSync(join(root, "terms.html"), "")

    const body = await website.sitemap().text()

    assertStringIncludes(body, "<loc>https://sandrone.example/</loc>")
    assertStringIncludes(
      body,
      "<loc>https://sandrone.example/privacy.html</loc>",
    )
    for (
      const skipped of ["404.html", "meta-example", "style.css", "terms"]
    ) {
      assertEquals(body.includes(skipped), false, skipped)
    }
  }),
)

Deno.test(
  "robots points at the sitemap and hides downloads",
  withWebRoot(async () => {
    const body = await website.robots().text()

    assertStringIncludes(
      body,
      "Sitemap: https://sandrone.example/sitemap.xml",
    )
    assertStringIncludes(body, "Disallow: /d/")
    assertStringIncludes(body, "Disallow: /api/")
  }),
)

Deno.test("old links redirect where they used to", async () => {
  const handler = website.createHandler()
  const status = await get(handler, "/status")
  const support = await get(handler, "/support")

  assertEquals(status.status, 301)
  assertEquals(status.headers.get("location"), "/shards")
  assertEquals(
    support.headers.get("location"),
    "https://discord.gg/N8gCjS294R",
  )
})

Deno.test("a hosted download is served from under /d/", async () => {
  const root = tempDir()
  const restore = patch(config, { downloadsDir: root })
  try {
    const slot = downloads.newSlot()
    Deno.writeTextFileSync(join(slot, "video file.mp4"), "video")
    const handler = website.createHandler()

    const found = await get(
      handler,
      `/d/${basename(slot)}/video%20file.mp4`,
    )
    assertEquals(found.status, 200)
    assertEquals(await found.text(), "video")

    const hidden = await get(
      handler,
      `/d/${basename(slot)}/.sandrone-download`,
    )
    await hidden.body?.cancel()
    assertEquals(hidden.status, 404)

    const escaped = await get(handler, `/d/${basename(slot)}/..%2F..%2Fx`)
    await escaped.body?.cancel()
    assertEquals(escaped.status, 404)
  } finally {
    restore()
  }
})

Deno.test("only GET and HEAD are answered", async () => {
  const handler = website.createHandler()
  const response = await handler(
    new Request("http://localhost/", { method: "POST" }),
  )
  await response.body?.cancel()

  assertEquals(response.status, 405)
})
