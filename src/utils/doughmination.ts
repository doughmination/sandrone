/* src/utils/doughmination.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { NotFoundError, UpstreamError } from "./failures.ts"

export const profileBase = "https://doughmination.uk/v2/discord"
export const genshinBase = "https://doughmination.uk/v2/genshin"

export class ProfileNotFoundError extends NotFoundError {
  override name = "ProfileNotFoundError"
}

export class GenshinNotFoundError extends NotFoundError {
  override name = "GenshinNotFoundError"
}

interface ApiBody {
  success?: boolean
  data?: unknown
  error?: {
    code?: string
    message?: string
  }
}

// deno-lint-ignore no-explicit-any
type Json = Record<string, any>

async function getJson(
  url: string,
  NotFound: typeof NotFoundError,
): Promise<Json> {
  const response = await fetch(url)
  const body = await response.json() as ApiBody

  if (!body.success || body.data === null || body.data === undefined) {
    const message = body.error?.message ?? "Unknown API error"
    if (response.status === 404 || body.error?.code === "not_found") {
      throw new NotFound(message)
    }
    throw new UpstreamError(
      `Doughmination API error: ${message}`,
      response.status,
    )
  }
  return body.data as Json
}

export const dough = {
  getProfile(userId: string): Promise<Json> {
    return getJson(`${profileBase}/users/${userId}`, ProfileNotFoundError)
  },

  getGenshinRoster(uid: string): Promise<Json> {
    return getJson(`${genshinBase}/roster/${uid}`, GenshinNotFoundError)
  },

  getGenshinCharacter(uid: string, heroId: string): Promise<Json> {
    return getJson(
      `${genshinBase}/roster/${uid}/${heroId}`,
      GenshinNotFoundError,
    )
  },
}
