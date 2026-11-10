/* src/framework.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import type {
  AutocompleteInteraction,
  ChatInputCommandInteraction,
  Client,
  ClientEvents,
  Interaction,
  MessageComponentInteraction,
  ModalSubmitInteraction,
  PermissionsString,
  RESTPostAPIChatInputApplicationCommandsJSONBody,
} from "discord.js"

export type Awaitable<T> = T | Promise<T>

export type Timer = ReturnType<typeof setInterval>

// Throws a CheckFailure (or subclass) to refuse; returning means allowed
export type Check = (
  interaction: ChatInputCommandInteraction,
) => Awaitable<void>

export interface Cooldown {
  rate: number
  per: number
}

export interface Action {
  run(interaction: ChatInputCommandInteraction): Awaitable<void>
  autocomplete?(interaction: AutocompleteInteraction): Awaitable<void>

  // Rolls the sassy refusal before anything else
  sassy?: boolean

  // Bot permissions; listed by `debug perms`
  botPermissions?: PermissionsString[]

  // Refuse in DMs, even when botPermissions is empty
  guildOnly?: boolean

  checks?: Check[]

  // Leave out for the default; null turns cooldowns off entirely
  cooldown?: Cooldown | null
}

interface JsonBuilder {
  toJSON(): RESTPostAPIChatInputApplicationCommandsJSONBody
}

export interface SlashCommand {
  data: JsonBuilder

  // For a command without subcommands
  action?: Action

  // Keyed "sub" or "group sub", matching the qualified name after the root
  subcommands?: Record<string, Action>
}

type AnyComponent = MessageComponentInteraction | ModalSubmitInteraction

// Stands in for discord.py's DynamicItem: matched on custom_id, any time
export interface ComponentHandler {
  pattern: RegExp
  run(interaction: AnyComponent, match: RegExpMatchArray): Awaitable<void>
}

export interface ModuleContext {
  readonly client: Client
  readonly name: string

  // Listeners are removed for you when the module unloads
  on<Event extends keyof ClientEvents>(
    event: Event,
    listener: (...args: ClientEvents[Event]) => Awaitable<void>,
  ): void

  // A repeating task, cancelled for you when the module unloads
  every(
    milliseconds: number,
    task: () => Awaitable<void>,
    options?: { label?: string; waitUntilReady?: boolean },
  ): void

  // Runs on unload, after listeners and tasks are cleared
  onTeardown(cleanup: () => Awaitable<void>): void
}

export interface Module {
  commands?: SlashCommand[]
  components?: ComponentHandler[]
  setup?(context: ModuleContext): Awaitable<void>
}

export function defineModule(module: Module): Module {
  return module
}

// "cog load", "mod add", "help" — same as discord.py's qualified_name
export function qualifiedName(interaction: Interaction): string | null {
  if (!interaction.isCommand() && !interaction.isAutocomplete()) {
    return null
  }
  const parts = [interaction.commandName]
  if (interaction.isChatInputCommand() || interaction.isAutocomplete()) {
    const group = interaction.options.getSubcommandGroup(false)
    const sub = interaction.options.getSubcommand(false)
    if (group) {
      parts.push(group)
    }
    if (sub) {
      parts.push(sub)
    }
  }
  return parts.join(" ")
}

// The Action a chat-input or autocomplete interaction is aimed at
export function actionFor(
  command: SlashCommand,
  interaction: ChatInputCommandInteraction | AutocompleteInteraction,
): Action | undefined {
  if (command.action) {
    return command.action
  }
  const group = interaction.options.getSubcommandGroup(false)
  const sub = interaction.options.getSubcommand(false)
  const key = [group, sub].filter(Boolean).join(" ")
  return command.subcommands?.[key]
}

export interface ListedAction {
  qualifiedName: string
  description: string
  action: Action
}

interface JsonOption {
  type: number
  name: string
  description: string
  options?: JsonOption[]
}

const subcommandType = 1
const subcommandGroupType = 2

// Every runnable command, flattened; used by /help and `debug perms`
export function listActions(command: SlashCommand): ListedAction[] {
  const json = command.data.toJSON()
  if (command.action) {
    return [
      {
        qualifiedName: json.name,
        description: json.description,
        action: command.action,
      },
    ]
  }

  const listed: ListedAction[] = []
  const visit = (options: JsonOption[] | undefined, path: string[]) => {
    for (const option of options ?? []) {
      if (option.type === subcommandGroupType) {
        visit(option.options, [...path, option.name])
      } else if (option.type === subcommandType) {
        const key = [...path, option.name].join(" ")
        const action = command.subcommands?.[key]
        if (action) {
          listed.push({
            qualifiedName: `${json.name} ${key}`,
            description: option.description,
            action,
          })
        }
      }
    }
  }
  visit(json.options as JsonOption[] | undefined, [])
  return listed
}
