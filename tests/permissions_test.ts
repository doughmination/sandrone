/* tests/permissions_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assertEquals, assertThrows } from "@std/assert"
import { PermissionsBitField, type PermissionsString } from "discord.js"
import { formatPermissions, hasPermissions } from "../src/checks.ts"
import {
  BotMissingPermissions,
  NoPrivateMessage,
} from "../src/utils/failures.ts"

function inGuild(...granted: PermissionsString[]) {
  return {
    guild: {},
    appPermissions: new PermissionsBitField(granted),
  }
}

const inDms = {
  guild: null,
  appPermissions: null,
}

Deno.test("checks application permissions", () => {
  assertThrows(
    () => hasPermissions(["EmbedLinks"])(inGuild()),
    BotMissingPermissions,
  )
})

Deno.test("the bot holding the permission passes", () => {
  assertEquals(
    hasPermissions(["AttachFiles"])(inGuild("AttachFiles")),
    true,
  )
})

Deno.test("guild only check still rejects dms", () => {
  assertThrows(
    () => hasPermissions(["EmbedLinks"], { guildOnly: true })(inDms),
    NoPrivateMessage,
  )
})

Deno.test("dms are allowed when not guild only", () => {
  assertEquals(hasPermissions(["EmbedLinks"])(inDms), true)
})

Deno.test("an unknown permission is refused up front", () => {
  assertThrows(
    () => hasPermissions(["BendSpoons" as PermissionsString]),
    TypeError,
  )
})

Deno.test("the missing permissions are carried on the error", () => {
  const error = assertThrows(
    () => hasPermissions(["AttachFiles", "EmbedLinks"])(inGuild()),
    BotMissingPermissions,
  )
  assertEquals(error.missingPermissions, ["AttachFiles", "EmbedLinks"])
})

Deno.test("permission names read like discord.py's did", () => {
  assertEquals(
    formatPermissions(["AttachFiles", "ManageGuild", "SendTTSMessages"]),
    "`Attach Files`, `Manage Server`, `Send TTS Messages`",
  )
})
