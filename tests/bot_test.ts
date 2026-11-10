/* tests/bot_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import {
  assert,
  assertEquals,
  assertRejects,
  assertStringIncludes,
} from "@std/assert"
import { Client, PermissionsBitField } from "discord.js"
import { dirname, join } from "@std/path"
import { Bot, ExtensionError } from "../src/bot.ts"
import { resetCooldowns } from "../src/checks.ts"
import { config } from "../src/config.ts"
import * as errors from "../src/utils/errors.ts"
import { isolate, patch, tempDir } from "./_helpers.ts"

const frameworkUrl = new URL("../src/framework.ts", import.meta.url).href

// A cog file importing the real framework, written into a temp src/ folder
function writeCog(sourceDir: string, handle: string, body: string): void {
  const path = join(sourceDir, "commands", "cogs", ...handle.split(".")) +
    ".ts"
  Deno.mkdirSync(dirname(path), { recursive: true })
  Deno.writeTextFileSync(
    path,
    `import { defineModule } from ${JSON.stringify(frameworkUrl)}\n` +
      `const builder = (name: string, description = "A thing") => ({\n` +
      `  toJSON: () => ({ name, description }),\n` +
      `})\n` +
      body,
  )
}

interface Sent {
  content?: string
  flags?: number
}

// Just enough of a ChatInputCommandInteraction for the dispatcher
function fakeCommand(
  commandName: string,
  options: { userId?: string; inGuild?: boolean } = {},
) {
  const sent: Sent[] = []
  const interaction = {
    commandName,
    customId: "",
    user: {
      id: options.userId ?? "1",
      username: "someone",
    },
    guild: options.inGuild ? { id: "10", name: "Server" } : null,
    guildId: options.inGuild ? "10" : null,
    channel: null,
    appPermissions: new PermissionsBitField([]),
    replied: false,
    deferred: false,
    options: {
      getSubcommandGroup: () => null,
      getSubcommand: () => null,
    },
    isChatInputCommand: () => true,
    isCommand: () => true,
    isAutocomplete: () => false,
    isMessageComponent: () => false,
    isModalSubmit: () => false,
    isRepliable: () => true,
    reply(message: Sent) {
      interaction.replied = true
      sent.push(message)
      return Promise.resolve()
    },
    followUp(message: Sent) {
      sent.push(message)
      return Promise.resolve()
    },
  }
  return {
    interaction,
    sent,
  }
}

async function withBot(
  test: (bot: Bot, sourceDir: string) => Promise<void>,
) {
  const sourceDir = tempDir()
  const restore = patch(config, {
    sourceDir,
    commandsDir: join(sourceDir, "commands"),
    settingsDir: join(sourceDir, "commands", "settings"),
    cogsDir: join(sourceDir, "commands", "cogs"),
    cogStatePath: join(sourceDir, "cog_state.json"),
  })
  const client = new Client({ intents: [] })
  isolate(errors.db)
  resetCooldowns()
  try {
    await test(new Bot(client), sourceDir)
  } finally {
    restore()
    await client.destroy()
  }
}

const pingCog = `
export default defineModule({
  commands: [
    {
      data: builder("ping"),
      action: {
        cooldown: { rate: 1, per: 60 },
        async run(interaction) {
          await interaction.reply({ content: "pong" })
        },
      },
    },
  ],
  setup(context) {
    context.on("messageCreate", () => {})
  },
})
`

Deno.test("a cog loads, registers its command and its listeners", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(sourceDir, "fun.ping", pingCog)
    await bot.loadExtension("commands.cogs.fun.ping")

    assertEquals(
      bot.commands().map(({ command }) => command.data.toJSON().name),
      [
        "ping",
      ],
    )
    assertEquals(bot.client.listenerCount("messageCreate"), 1)
  })
})

Deno.test("unloading a cog removes its command and its listeners", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(sourceDir, "fun.ping", pingCog)
    await bot.loadExtension("commands.cogs.fun.ping")
    await bot.unloadExtension("commands.cogs.fun.ping")

    assertEquals(bot.commands(), [])
    assertEquals(bot.client.listenerCount("messageCreate"), 0)
  })
})

Deno.test("two cogs cannot claim the same command name", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(sourceDir, "fun.ping", pingCog)
    writeCog(sourceDir, "tools.ping", pingCog)
    await bot.loadExtension("commands.cogs.fun.ping")

    await assertRejects(
      () => bot.loadExtension("commands.cogs.tools.ping"),
      ExtensionError,
      "already registered",
    )
    assertEquals(bot.client.listenerCount("messageCreate"), 1)
  })
})

Deno.test("a reload picks up the edited file", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(sourceDir, "fun.ping", pingCog)
    await bot.loadExtension("commands.cogs.fun.ping")
    writeCog(sourceDir, "fun.ping", pingCog.replace('"ping"', '"pong"'))
    await bot.reloadExtension("commands.cogs.fun.ping")

    assertEquals(
      bot.commands().map(({ command }) => command.data.toJSON().name),
      [
        "pong",
      ],
    )
  })
})

Deno.test("disabled cogs are skipped at startup", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(sourceDir, "fun.ping", pingCog)
    Deno.writeTextFileSync(
      join(sourceDir, "cog_state.json"),
      JSON.stringify({ disabled: ["fun.ping"] }),
    )
    await bot.loadAll()

    assertEquals(bot.extensions.size, 0)
  })
})

Deno.test("a command runs, then the cooldown stops a second go", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(sourceDir, "fun.ping", pingCog)
    await bot.loadExtension("commands.cogs.fun.ping")

    const first = fakeCommand("ping")
    // deno-lint-ignore no-explicit-any
    await bot.handleInteraction(first.interaction as any)
    assertEquals(first.sent[0].content, "pong")

    const second = fakeCommand("ping")
    // deno-lint-ignore no-explicit-any
    await bot.handleInteraction(second.interaction as any)
    assertStringIncludes(second.sent[0].content ?? "", "Slow down.")
  })
})

Deno.test("a crash is logged and the user gets a fault code", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(
      sourceDir,
      "fun.broken",
      `
export default defineModule({
  commands: [{
    data: builder("broken"),
    action: { run() { throw new Error("gears jammed") } },
  }],
})
`,
    )
    await bot.loadExtension("commands.cogs.fun.broken")

    const { interaction, sent } = fakeCommand("broken")
    // deno-lint-ignore no-explicit-any
    await bot.handleInteraction(interaction as any)

    assertStringIncludes(sent[0].content ?? "", "gears jammed")
    assertStringIncludes(sent[0].content ?? "", "Fault `MALFUNCTION-")
    assertEquals(errors.recent()[0].command, "broken")
  })
})

Deno.test("missing bot permissions are reported, not crashed on", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(
      sourceDir,
      "tools.qr",
      `
export default defineModule({
  commands: [{
    data: builder("qr"),
    action: {
      botPermissions: ["AttachFiles"],
      run() { throw new Error("should not run") },
    },
  }],
})
`,
    )
    await bot.loadExtension("commands.cogs.tools.qr")

    const { interaction, sent } = fakeCommand("qr", { inGuild: true })
    // deno-lint-ignore no-explicit-any
    await bot.handleInteraction(interaction as any)

    assertStringIncludes(
      sent[0].content ?? "",
      "I am missing `Attach Files`",
    )
    assert(errors.recent()[0].ref.startsWith("WORKSHOP-"))
  })
})

Deno.test("subcommands are routed by their qualified name", async () => {
  await withBot(async (bot, sourceDir) => {
    writeCog(
      sourceDir,
      "tools.group",
      `
export default defineModule({
  commands: [{
    data: { toJSON: () => ({ name: "cog", description: "x", options: [
      { type: 1, name: "load", description: "Load one" },
    ] }) },
    subcommands: {
      load: { async run(interaction) { await interaction.reply({ content: "loaded" }) } },
    },
  }],
})
`,
    )
    await bot.loadExtension("commands.cogs.tools.group")

    const { interaction, sent } = fakeCommand("cog")
    interaction.options.getSubcommand = () => "load" as unknown as null
    // deno-lint-ignore no-explicit-any
    await bot.handleInteraction(interaction as any)

    assertEquals(sent[0].content, "loaded")
  })
})
