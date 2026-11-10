/* src/client.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import chalk from "chalk"
import {
  ActivityType,
  Client,
  Events,
  GatewayIntentBits,
  Routes,
} from "discord.js"
import { Buffer } from "node:buffer"
import { join } from "@std/path"
import { Bot } from "./bot.ts"
import { config, requireToken } from "./config.ts"
import type { Timer } from "./framework.ts"
import * as downloads from "./utils/downloads.ts"
import * as errors from "./utils/errors.ts"
import * as storage from "./utils/storage.ts"
import * as website from "./website.ts"

// No message content is read: the only listener notes which channel was active
export function createClient(): Client {
  return new Client({
    intents: [
      GatewayIntentBits.Guilds,
      GatewayIntentBits.GuildMessages,
    ],
    presence: {
      activities: [
        {
          type: ActivityType.Listening,
          name: "I love Columbina <3",
        },
      ],
    },
  })
}

// Bots can't style their global profile, so it is set per server
export async function applyNameStyle(client: Client): Promise<void> {
  const fields: Record<string, unknown> = {}
  if (config.displayNameFont !== null) {
    fields.display_name_font_id = config.displayNameFont
  }
  if (config.displayNameEffect !== null) {
    fields.display_name_effect_id = config.displayNameEffect
  }
  if (config.displayNameColors !== null) {
    fields.display_name_colors = config.displayNameColors
  }
  if (Object.keys(fields).length === 0) {
    return
  }

  for (const guild of client.guilds.cache.values()) {
    try {
      await client.rest.patch(Routes.guildMember(guild.id, "@me"), {
        body: fields,
      })
      console.log(chalk.yellow(`[style] name style set in ${guild.name}`))
    } catch (error) {
      console.log(
        chalk.red(
          `[style] couldn't style my name in ${guild.id}: ${error}`,
        ),
      )
    }
  }
}

async function applyProfile(client: Client): Promise<void> {
  try {
    const avatar = await Deno.readFile(
      join(config.assetsDir, "avatar.png"),
    )
    const banner = await Deno.readFile(
      join(config.assetsDir, "banner.png"),
    )
    await client.user?.edit({
      avatar: Buffer.from(avatar),
      banner: Buffer.from(banner),
    })
    console.log(chalk.yellow("Avatar and Banner loaded!"))
  } catch (error) {
    console.log(chalk.red(`Failed to set avatar/banner: ${error}`))
  }
  await applyNameStyle(client)
}

export async function runBot(): Promise<void> {
  const client = createClient()
  const bot = new Bot(client)
  const timers: Timer[] = []

  client.on(Events.Error, (error) => {
    errors.record(error, {
      source: "event error",
    })
    console.log(chalk.red(`[client] ${error}`))
  })

  let profileSet = false
  client.on(Events.ClientReady, async (ready) => {
    console.log(chalk.magenta(`Logged in as ${ready.user.tag}`))
    if (profileSet) {
      return
    }
    profileSet = true

    try {
      await bot.syncCommands()
      console.log(
        chalk.green(`[startup] synced ${bot.commands().length} commands`),
      )
    } catch (error) {
      errors.record(error, {
        source: "command sync",
      })
      console.log(chalk.red(`[startup] command sync failed: ${error}`))
    }
    await applyProfile(client)
  })

  await bot.loadAll()

  website.startServer(bot)
  timers.push(downloads.sweepForever())
  timers.push(storage.flushForever())
  timers.push(bot.startHousekeeping())

  if (config.devMode) {
    bot.watchCogs().catch((error) =>
      console.log(chalk.red(`[dev-reload] watcher stopped: ${error}`))
    )
    console.log(
      chalk.magenta("[dev-reload] watching commands/cogs for changes"),
    )
  }

  let shuttingDown = false
  const shutdown = async (exitCode = 0) => {
    if (shuttingDown) {
      return
    }
    shuttingDown = true
    console.log(chalk.gray("\n[shutdown] closing bot..."))

    bot.stopWatching()
    for (const timer of timers) {
      clearInterval(timer)
    }
    for (const name of [...bot.extensions.keys()].reverse()) {
      await bot.unloadExtension(name).catch(() => {})
    }
    await client.destroy()
    await website.stopServer()
    for (const name of storage.saveAll()) {
      console.log(chalk.gray(`[shutdown] saved data/${name}.jp`))
    }
    console.log(chalk.gray("[shutdown] bot closed"))
    Deno.exit(exitCode)
  }
  const onSignal = () => shutdown(0)

  Deno.addSignalListener("SIGINT", onSignal)
  if (Deno.build.os === "windows") {
    Deno.addSignalListener("SIGBREAK", onSignal)
    console.log(
      chalk.blue("Windows machine detected, shutdown may not be graceful"),
    )
  } else {
    Deno.addSignalListener("SIGTERM", onSignal)
  }

  // A bad token still shuts down cleanly, so nothing unsaved is lost
  try {
    await client.login(requireToken())
  } catch (error) {
    console.log(chalk.red(`[startup] could not log in: ${error}`))
    await shutdown(1)
  }
}
