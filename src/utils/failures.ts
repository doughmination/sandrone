/* src/utils/failures.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import type { PermissionsString } from "discord.js"

// A check refused the command; the handler replies, nothing is logged
export class CheckFailure extends Error {
  override name = "CheckFailure"
}

// Sandrone already replied with a sassy refusal, so stay quiet
export class SassyDenial extends CheckFailure {
  override name = "SassyDenial"
}

export class NoPrivateMessage extends CheckFailure {
  override name = "NoPrivateMessage"

  constructor(message = "This command can only be used in a server.") {
    super(message)
  }
}

export class BotMissingPermissions extends CheckFailure {
  override name = "BotMissingPermissions"

  constructor(readonly missingPermissions: PermissionsString[]) {
    super(
      `Bot requires ${missingPermissions.join(", ")} permission(s) to ` +
        "run this command.",
    )
  }
}

export class MissingPermissions extends CheckFailure {
  override name = "MissingPermissions"

  constructor(readonly missingPermissions: PermissionsString[]) {
    super(
      `You are missing ${missingPermissions.join(", ")} permission(s) ` +
        "to run this command.",
    )
  }
}

export class CommandOnCooldown extends CheckFailure {
  override name = "CommandOnCooldown"

  constructor(readonly retryAfter: number) {
    super(`You are on cooldown. Try again in ${retryAfter.toFixed(2)}s`)
  }
}

// An outside API answered, but not with what was asked for
export class UpstreamError extends Error {
  override name = "UpstreamError"

  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message)
  }
}

// What was looked up does not exist upstream
export class NotFoundError extends Error {
  override name = "NotFoundError"
}

// Whatever was thrown, as an Error the log can read
export function toError(value: unknown): Error {
  if (value instanceof Error) {
    return value
  }
  return new Error(typeof value === "string" ? value : String(value))
}
