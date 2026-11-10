/* tests/config_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assertEquals } from "@std/assert"
import { join } from "@std/path"
import {
  config,
  discoverCogHandles,
  discoverModules,
} from "../src/config.ts"
import { tempDir } from "./_helpers.ts"

const configUrl = new URL("../src/config.ts", import.meta.url).href

// config.ts reads the environment once, so each case gets its own process
async function configUnder(env: Record<string, string>) {
  const script = `
    const { config } = await import(${JSON.stringify(configUrl)})
    console.log(JSON.stringify(config))
  `
  const output = await new Deno.Command(Deno.execPath(), {
    args: [
      "eval",
      "--config",
      join(config.repoRoot, "deno.json"),
      script,
    ],
    env,
    clearEnv: true,
  }).output()
  return JSON.parse(new TextDecoder().decode(output.stdout))
}

for (const value of ["", "   "]) {
  Deno.test(`blank download settings use defaults (${JSON.stringify(value)})`, async () => {
    const loaded = await configUnder({
      DOWNLOADS_DIR: value,
      DOWNLOADS_URL: value,
      DOWNLOADS_PORT: "2020",
    })

    assertEquals(loaded.downloadsDir, join(config.repoRoot, "downloads"))
    assertEquals(loaded.downloadsUrl, "http://localhost:2020")
  })
}

Deno.test("trailing slashes are trimmed off public urls", async () => {
  const loaded = await configUnder({
    DOWNLOADS_URL: "https://files.example.com///",
  })

  assertEquals(loaded.downloadsUrl, "https://files.example.com")
  assertEquals(loaded.siteUrl, "https://files.example.com")
})

Deno.test("cog handles keep the Python bot's dotted names", () => {
  const root = tempDir()
  Deno.mkdirSync(join(root, "fun"))
  Deno.mkdirSync(join(root, "media"))
  Deno.writeTextFileSync(join(root, "fun", "judge.ts"), "")
  Deno.writeTextFileSync(join(root, "media", "pride.ts"), "")
  Deno.writeTextFileSync(join(root, "snippets.ts"), "")
  Deno.writeTextFileSync(join(root, "fun", "judge_test.ts"), "")
  Deno.writeTextFileSync(join(root, "fun", "_shared.ts"), "")

  assertEquals(discoverCogHandles(root), [
    "fun.judge",
    "media.pride",
    "snippets",
  ])
})

Deno.test("top level modules ignore nested folders", () => {
  const root = tempDir()
  Deno.mkdirSync(join(root, "cogs"))
  Deno.writeTextFileSync(join(root, "help.ts"), "")
  Deno.writeTextFileSync(join(root, "cogs", "judge.ts"), "")

  assertEquals(discoverModules(root, "commands"), ["commands.help"])
})

Deno.test("a missing cogs folder means no cogs, not a crash", () => {
  assertEquals(discoverCogHandles(join(tempDir(), "nope")), [])
})
