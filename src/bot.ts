/* src/bot.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import chalk from "chalk"
import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
  Client,
  ClientEvents,
  Interaction,
  MessageComponentInteraction,
  ModalSubmitInteraction,
  RESTPostAPIChatInputApplicationCommandsJSONBody,
} from "discord.js"
import { join, relative, SEPARATOR, toFileUrl } from "@std/path"
import {
  checkCooldown,
  cooldownOf,
  handleCommandError,
  hasPermissions,
  pruneCooldowns,
  respond,
  validatePermissions,
} from "./checks.ts"
import {
  config,
  discoverCogHandles,
  discoverModules,
  loadDisabled,
} from "./config.ts"
import {
  actionFor,
  type Awaitable,
  type ComponentHandler,
  type Module,
  type ModuleContext,
  qualifiedName,
  type SlashCommand,
  type Timer,
} from "./framework.ts"
import { sassyCheck } from "./mood.ts"
import * as errors from "./utils/errors.ts"

export const cogsPrefix = "commands.cogs."

export class ExtensionError extends Error {
  override name = "ExtensionError"
}

interface LoadedExtension {
  name: string
  module: Module
  listeners: Array<[keyof ClientEvents, (...args: unknown[]) => void]>
  timers: Timer[]
  cleanups: Array<() => Awaitable<void>>
}

export interface RegisteredCommand {
  extension: string
  command: SlashCommand
}

export interface ShardStatus {
  id: number
  guilds: number
  latency: number | null
}

// "commands.cogs.fun.judge" lives at src/commands/cogs/fun/judge.ts
export function extensionPath(name: string): string {
  return join(config.sourceDir, ...name.split(".")) + ".ts"
}

export function discoverExtensions(): string[] {
  return [
    ...discoverModules(config.commandsDir, "commands"),
    ...discoverModules(config.settingsDir, "commands.settings"),
    ...discoverCogHandles().map((handle) => cogsPrefix + handle),
  ]
}

function isModule(value: unknown): value is Module {
  return typeof value === "object" && value !== null
}

// discord.py allowed every context and install type by default
function withDefaults(
  json: RESTPostAPIChatInputApplicationCommandsJSONBody,
): RESTPostAPIChatInputApplicationCommandsJSONBody {
  return {
    ...json,
    contexts: json.contexts ?? [0, 1, 2],
    integration_types: json.integration_types ?? [0, 1],
  }
}

function finite(milliseconds: number): number | null {
  return Number.isFinite(milliseconds) && milliseconds >= 0
    ? Math.round(milliseconds)
    : null
}

export class Bot {
  readonly startedAt = Date.now()
  readonly extensions = new Map<string, LoadedExtension>()
  private readonly commandRegistry = new Map<string, RegisteredCommand>()
  private readonly componentRegistry: Array<{
    extension: string
    handler: ComponentHandler
  }> = []
  private watcher: Deno.FsWatcher | null = null

  constructor(readonly client: Client) {
    client.on("interactionCreate", (interaction) => {
      this.handleInteraction(interaction).catch((error) => {
        errors.record(error, {
          source: "event interactionCreate",
        })
        console.log(chalk.red(`[interaction] ${error}`))
      })
    })
  }

  commands(): RegisteredCommand[] {
    return [...this.commandRegistry.values()]
  }

  // -- loading ------------------------------------------------------------

  async loadExtension(name: string, fresh = false): Promise<void> {
    if (this.extensions.has(name)) {
      throw new ExtensionError(`Extension '${name}' is already loaded.`)
    }

    let module: unknown
    try {
      const url = toFileUrl(extensionPath(name)).href
      const imported = await import(fresh ? `${url}?v=${Date.now()}` : url)
      module = imported.default
    } catch (error) {
      throw new ExtensionError(
        `Extension '${name}' failed to import: ${error}`,
      )
    }
    if (!isModule(module)) {
      throw new ExtensionError(
        `Extension '${name}' has no default export from defineModule().`,
      )
    }

    for (const command of module.commands ?? []) {
      const commandName = command.data.toJSON().name
      const owner = this.commandRegistry.get(commandName)
      if (owner) {
        throw new ExtensionError(
          `/${commandName} from '${name}' is already registered by ` +
            `'${owner.extension}'.`,
        )
      }
      for (const action of Object.values(command.subcommands ?? {})) {
        validatePermissions(action.botPermissions ?? [])
      }
      validatePermissions(command.action?.botPermissions ?? [])
    }

    const loaded: LoadedExtension = {
      name,
      module,
      listeners: [],
      timers: [],
      cleanups: [],
    }

    try {
      await module.setup?.(this.contextFor(loaded))
    } catch (error) {
      await this.tearDown(loaded)
      throw new ExtensionError(
        `Extension '${name}' failed to set up: ${error}`,
      )
    }

    for (const command of module.commands ?? []) {
      this.commandRegistry.set(command.data.toJSON().name, {
        extension: name,
        command,
      })
    }
    for (const handler of module.components ?? []) {
      this.componentRegistry.push({
        extension: name,
        handler,
      })
    }
    this.extensions.set(name, loaded)
  }

  async unloadExtension(name: string): Promise<void> {
    const loaded = this.extensions.get(name)
    if (!loaded) {
      throw new ExtensionError(`Extension '${name}' has not been loaded.`)
    }

    this.extensions.delete(name)
    for (const [commandName, entry] of this.commandRegistry) {
      if (entry.extension === name) {
        this.commandRegistry.delete(commandName)
      }
    }
    for (
      let index = this.componentRegistry.length - 1;
      index >= 0;
      index--
    ) {
      if (this.componentRegistry[index].extension === name) {
        this.componentRegistry.splice(index, 1)
      }
    }
    await this.tearDown(loaded)
  }

  async reloadExtension(name: string): Promise<void> {
    if (this.extensions.has(name)) {
      await this.unloadExtension(name)
    }
    await this.loadExtension(name, true)
  }

  async loadAll(): Promise<void> {
    const disabled = loadDisabled()
    for (const extension of discoverExtensions()) {
      if (
        extension.startsWith(cogsPrefix) &&
        disabled.has(extension.slice(cogsPrefix.length))
      ) {
        console.log(
          chalk.gray(
            `[startup] skipped ${extension} (disabled via /cog unload)`,
          ),
        )
        continue
      }

      try {
        await this.loadExtension(extension)
        console.log(chalk.green(`[startup] loaded ${extension}`))
      } catch (error) {
        console.log(
          chalk.red(`[startup] failed to load ${extension}: ${error}`),
        )
      }
    }
  }

  private contextFor(loaded: LoadedExtension): ModuleContext {
    const client = this.client
    return {
      client,
      name: loaded.name,

      on(event, listener) {
        const wrapped = (...args: unknown[]) => {
          Promise.resolve()
            .then(() =>
              (listener as (...a: unknown[]) => unknown)(...args)
            )
            .catch((error) => {
              errors.record(error, {
                source: `event ${event}`,
              })
              console.log(
                chalk.red(`[${loaded.name}] ${event} listener: ${error}`),
              )
            })
        }
        client.on(event, wrapped)
        loaded.listeners.push([event, wrapped])
      },

      every(milliseconds, task, options = {}) {
        const label = options.label ?? loaded.name
        const waitUntilReady = options.waitUntilReady ?? true
        const timer = setInterval(() => {
          if (waitUntilReady && !client.isReady()) {
            return
          }
          Promise.resolve()
            .then(task)
            .catch((error) => {
              errors.record(error, {
                source: label,
              })
              console.log(chalk.red(`[${label}] task failed: ${error}`))
            })
        }, milliseconds)
        loaded.timers.push(timer)
      },

      onTeardown(cleanup) {
        loaded.cleanups.push(cleanup)
      },
    }
  }

  private async tearDown(loaded: LoadedExtension): Promise<void> {
    for (const [event, listener] of loaded.listeners) {
      this.client.off(event, listener)
    }
    for (const timer of loaded.timers) {
      clearInterval(timer)
    }
    for (const cleanup of loaded.cleanups) {
      try {
        await cleanup()
      } catch (error) {
        console.log(chalk.red(`[${loaded.name}] teardown: ${error}`))
      }
    }
    loaded.listeners = []
    loaded.timers = []
    loaded.cleanups = []
  }

  // -- syncing ------------------------------------------------------------

  async syncCommands(): Promise<void> {
    const application = this.client.application
    if (!application) {
      throw new Error("Cannot sync commands before the client is ready.")
    }
    const body = this.commands().map(({ command }) =>
      withDefaults(command.data.toJSON())
    )
    await application.commands.set(body)
  }

  // -- status (read by the website) ----------------------------------------

  guildCount(): number {
    return this.client.guilds.cache.size
  }

  latency(): number | null {
    return finite(this.client.ws.ping)
  }

  shards(): ShardStatus[] {
    const shardCount = this.client.ws.shards.size || 1
    const statuses: ShardStatus[] = []
    for (let id = 0; id < shardCount; id++) {
      const shard = this.client.ws.shards.get(id)
      const guilds = this.client.guilds.cache.filter(
        (guild) => guild.shardId === id,
      ).size
      statuses.push({
        id,
        guilds,
        latency: shard ? finite(shard.ping) : this.latency(),
      })
    }
    return statuses
  }

  // -- dispatch -----------------------------------------------------------

  async handleInteraction(interaction: Interaction): Promise<void> {
    if (interaction.isChatInputCommand()) {
      await this.runCommand(interaction)
    } else if (interaction.isAutocomplete()) {
      await this.runAutocomplete(interaction)
    } else if (
      interaction.isMessageComponent() || interaction.isModalSubmit()
    ) {
      await this.runComponent(interaction)
    }
  }

  private async runCommand(
    interaction: ChatInputCommandInteraction,
  ): Promise<void> {
    const entry = this.commandRegistry.get(interaction.commandName)
    const action = entry
      ? actionFor(entry.command, interaction)
      : undefined
    if (!action) {
      await respond(interaction, "That command is not loaded right now.")
      return
    }

    try {
      if (action.sassy) {
        await sassyCheck(interaction)
      }
      if (action.guildOnly || action.botPermissions?.length) {
        hasPermissions(action.botPermissions ?? [], {
          guildOnly: action.guildOnly,
        })(interaction)
      }
      for (const check of action.checks ?? []) {
        await check(interaction)
      }
      checkCooldown(
        qualifiedName(interaction) ?? interaction.commandName,
        interaction.user.id,
        cooldownOf(action),
      )

      await action.run(interaction)
    } catch (error) {
      await handleCommandError(interaction, error)
    }
  }

  private async runAutocomplete(
    interaction: AutocompleteInteraction,
  ): Promise<void> {
    const entry = this.commandRegistry.get(interaction.commandName)
    const action = entry
      ? actionFor(entry.command, interaction)
      : undefined
    try {
      if (action?.autocomplete) {
        await action.autocomplete(interaction)
      } else if (!interaction.responded) {
        await interaction.respond([])
      }
    } catch (error) {
      errors.record(error, {
        source: "autocomplete",
        command: qualifiedName(interaction),
        guild: interaction.guild,
        channel: interaction.channel,
        user: interaction.user,
      })
      if (!interaction.responded) {
        await interaction.respond([]).catch(() => {})
      }
    }
  }

  private async runComponent(
    interaction: MessageComponentInteraction | ModalSubmitInteraction,
  ): Promise<void> {
    for (const { handler } of this.componentRegistry) {
      const match = interaction.customId.match(handler.pattern)
      if (!match) {
        continue
      }
      try {
        await handler.run(interaction, match)
      } catch (error) {
        const logged = errors.record(error, {
          source: "component",
          command: interaction.customId,
          guild: interaction.guild,
          channel: interaction.channel,
          user: interaction.user,
        })
        await respond(
          interaction,
          `Something went wrong: ${(error as Error).message ?? error}` +
            errors.note(logged),
        )
      }
      return
    }
  }

  // -- housekeeping -------------------------------------------------------

  startHousekeeping(): Timer {
    return setInterval(pruneCooldowns, 600_000)
  }

  // Dev mode: reload a cog whenever its file changes
  async watchCogs(): Promise<void> {
    this.watcher = Deno.watchFs(config.cogsDir, { recursive: true })
    let pending = new Set<string>()
    let timer: ReturnType<typeof setTimeout> | undefined

    const flush = async () => {
      const paths = pending
      pending = new Set()
      const disabled = loadDisabled()
      let reloaded = false

      for (const path of paths) {
        const handle = relative(config.cogsDir, path)
          .slice(0, -3)
          .split(SEPARATOR)
          .join(".")
        if (disabled.has(handle)) {
          console.log(
            chalk.gray(
              `[dev-reload] skipped ${cogsPrefix}${handle} (disabled via ` +
                "/cog unload)",
            ),
          )
          continue
        }

        const extension = cogsPrefix + handle
        try {
          await this.reloadExtension(extension)
          reloaded = true
          console.log(chalk.gray(`[dev-reload] reloaded ${extension}`))
        } catch (error) {
          console.log(
            chalk.red(
              `[dev-reload] failed to reload ${extension}: ${error}`,
            ),
          )
        }
      }

      if (reloaded && this.client.isReady()) {
        await this.syncCommands()
      }
    }

    for await (const event of this.watcher) {
      if (event.kind !== "modify" && event.kind !== "create") {
        continue
      }
      for (const path of event.paths) {
        const name = path.split(SEPARATOR).at(-1) ?? ""
        if (
          name.endsWith(".ts") &&
          !name.endsWith("_test.ts") &&
          !name.startsWith("_")
        ) {
          pending.add(path)
        }
      }
      clearTimeout(timer)
      timer = setTimeout(() => {
        flush().catch((error) =>
          console.log(chalk.red(`[dev-reload] ${error}`))
        )
      }, 300)
    }
  }

  stopWatching(): void {
    this.watcher?.close()
    this.watcher = null
  }
}
