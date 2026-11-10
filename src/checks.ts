/* src/checks.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import chalk from "chalk"
import {
  type ChatInputCommandInteraction,
  type InteractionReplyOptions,
  MessageFlags,
  PermissionFlagsBits,
  type PermissionsString,
} from "discord.js"
import { config } from "./config.ts"
import {
  type Action,
  type Check,
  type Cooldown,
  qualifiedName,
} from "./framework.ts"
import * as errors from "./utils/errors.ts"
import {
  BotMissingPermissions,
  CheckFailure,
  CommandOnCooldown,
  MissingPermissions,
  NoPrivateMessage,
  SassyDenial,
  toError,
} from "./utils/failures.ts"

// Every command gets this unless it sets its own `cooldown`
export const defaultCooldown: Cooldown = {
  rate: 3,
  per: 10,
}

// discord.py's app_commands.Cooldown, token for token
export class CooldownBucket {
  private tokens: number
  private window = 0
  private last = 0

  constructor(
    readonly rate: number,
    readonly per: number,
  ) {
    this.tokens = rate
  }

  private tokensAt(now: number): number {
    return now > this.window + this.per ? this.rate : this.tokens
  }

  // Seconds left to wait, or null when the use was allowed
  use(now: number = Date.now() / 1000): number | null {
    this.last = now
    this.tokens = this.tokensAt(now)
    if (this.tokens === this.rate) {
      this.window = now
    }
    if (this.tokens === 0) {
      return this.per - (now - this.window)
    }
    this.tokens -= 1
    return null
  }

  isStale(now: number = Date.now() / 1000): boolean {
    return now > this.last + this.per
  }
}

const buckets = new Map<string, Map<string, CooldownBucket>>()

export function cooldownOf(action: Action): Cooldown | null {
  return action.cooldown === undefined ? defaultCooldown : action.cooldown
}

// Each user gets their own bucket; owners are never held back
export function checkCooldown(
  commandName: string,
  userId: string,
  limit: Cooldown | null,
  now?: number,
): void {
  if (limit === null || config.owners.includes(userId)) {
    return
  }

  let perUser = buckets.get(commandName)
  if (perUser === undefined) {
    perUser = new Map()
    buckets.set(commandName, perUser)
  }

  let bucket = perUser.get(userId)
  if (
    bucket === undefined ||
    bucket.rate !== limit.rate ||
    bucket.per !== limit.per
  ) {
    bucket = new CooldownBucket(limit.rate, limit.per)
    perUser.set(userId, bucket)
  }

  const retryAfter = bucket.use(now)
  if (retryAfter !== null) {
    throw new CommandOnCooldown(retryAfter)
  }
}

// Drops buckets nobody has touched for a full window
export function pruneCooldowns(): void {
  for (const [commandName, perUser] of buckets) {
    for (const [userId, bucket] of perUser) {
      if (bucket.isStale()) {
        perUser.delete(userId)
      }
    }
    if (perUser.size === 0) {
      buckets.delete(commandName)
    }
  }
}

export function resetCooldowns(): void {
  buckets.clear()
}

const knownPermissions = new Set(Object.keys(PermissionFlagsBits))

export function validatePermissions(permissions: string[]): void {
  const invalid = permissions.filter((name) => !knownPermissions.has(name))
  if (invalid.length) {
    throw new TypeError(
      `Invalid permission(s): ${invalid.sort().join(", ")}`,
    )
  }
}

interface PermissionTarget {
  guild: unknown
  appPermissions: { has(permission: PermissionsString): boolean } | null
}

// Require the bot to hold `permissions` wherever the command was run
export function hasPermissions(
  permissions: PermissionsString[],
  options: { guildOnly?: boolean } = {},
): (interaction: PermissionTarget) => true {
  validatePermissions(permissions)

  return (interaction) => {
    if (interaction.guild === null || interaction.guild === undefined) {
      if (options.guildOnly) {
        throw new NoPrivateMessage()
      }
      return true
    }

    const granted = interaction.appPermissions
    const missing = permissions.filter(
      (permission) => !granted?.has(permission),
    )
    if (missing.length) {
      throw new BotMissingPermissions(missing)
    }
    return true
  }
}

export const ownerOnly: Check = (interaction) => {
  if (!config.owners.includes(interaction.user.id)) {
    throw new CheckFailure("Owner only.")
  }
}

// "ManageGuild" reads as `Manage Server`, "SendTTSMessages" as `Send TTS Messages`
export function formatPermissions(permissions: string[]): string {
  return permissions
    .map((permission) => {
      const words = permission
        .split(/(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])/)
        .map((word) => word === "Guild" ? "Server" : word)
      return `\`${words.join(" ")}\``
    })
    .join(", ")
}

// Anything that can be replied to: commands, buttons, menus, modals
export interface Replyable {
  replied: boolean
  deferred: boolean
  reply(options: InteractionReplyOptions): Promise<unknown>
  followUp(options: InteractionReplyOptions): Promise<unknown>
}

export async function respond(
  interaction: Replyable,
  message: string,
): Promise<void> {
  const payload = {
    content: message,
    flags: MessageFlags.Ephemeral as const,
  }
  try {
    if (interaction.replied || interaction.deferred) {
      await interaction.followUp(payload)
    } else {
      await interaction.reply(payload)
    }
  } catch (error) {
    console.log(
      chalk.red(`[error] could not reply with an error: ${error}`),
    )
  }
}

export async function handleCommandError(
  interaction: ChatInputCommandInteraction,
  thrown: unknown,
): Promise<void> {
  const error = toError(thrown)

  if (error instanceof BotMissingPermissions) {
    const logged = errors.fromInteraction(interaction, error)
    await respond(
      interaction,
      `I am missing ${formatPermissions(error.missingPermissions)} to ` +
        `run this command.${errors.note(logged)}`,
    )
    return
  }

  if (error instanceof MissingPermissions) {
    await respond(
      interaction,
      `You are missing ${formatPermissions(error.missingPermissions)} ` +
        "to run this command.",
    )
    return
  }

  if (error instanceof NoPrivateMessage) {
    await respond(
      interaction,
      "This command can only be used in a server.",
    )
    return
  }

  if (error instanceof CommandOnCooldown) {
    await respond(
      interaction,
      `Slow down. Try again in ${Math.ceil(error.retryAfter)}s.`,
    )
    return
  }

  if (error instanceof SassyDenial) {
    return
  }

  if (error instanceof CheckFailure) {
    await respond(
      interaction,
      "You do not have permission to execute this command",
    )
    return
  }

  const name = qualifiedName(interaction) ?? "unknown"
  const logged = errors.fromInteraction(interaction, error)
  console.log(
    chalk.red(
      `[error] unhandled error in ${name}: ${error.stack ?? error}`,
    ),
  )
  await respond(
    interaction,
    `Something went wrong running \`${name}\`: ${error.message}` +
      errors.note(logged),
  )
}
