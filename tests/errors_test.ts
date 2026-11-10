/* tests/errors_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import {
  assert,
  assertEquals,
  assertNotEquals,
  assertStringIncludes,
} from "@std/assert"
import { DiscordAPIError } from "discord.js"
import * as errors from "../src/utils/errors.ts"
import {
  BotMissingPermissions,
  UpstreamError,
} from "../src/utils/failures.ts"
import { isolate } from "./_helpers.ts"

function boom(message = "kaboom"): Error {
  return new Error(message)
}

function logged(
  error: Error,
  options: errors.RecordOptions,
): errors.Entry {
  const entry = errors.record(error, options)
  assert(entry !== null)
  return entry
}

function codeFor(error: Error): string {
  return errors.codeOf(error, "slash command")
}

function discordError(status: number): DiscordAPIError {
  return new DiscordAPIError(
    {
      message: "nope",
      code: 0,
    },
    0,
    status,
    "POST",
    "/channels/1/messages",
    {},
  )
}

Deno.test("a recorded error keeps what debug needs to show", () => {
  isolate(errors.db)
  errors.record(boom(), {
    source: "slash command",
    command: "qr",
  })

  const [entry] = errors.recent()
  assertEquals(entry.kind, "Error")
  assertEquals(entry.text, "kaboom")
  assertEquals(entry.command, "qr")
  assertStringIncludes(entry.trace, "Error: kaboom")
})

Deno.test("the newest error comes first", () => {
  isolate(errors.db)
  for (const name of ["first", "second", "third"]) {
    errors.record(boom(name), { source: "event messageCreate" })
  }

  assertEquals(errors.recent().map((entry) => entry.text), [
    "third",
    "second",
    "first",
  ])
})

Deno.test("the log stops growing at the keep limit", () => {
  isolate(errors.db)
  for (let index = 0; index < errors.keepLimit + 10; index++) {
    errors.record(boom(), {
      source: "event messageCreate",
      command: "cmd" + "a".repeat(index),
    })
  }

  assertEquals(errors.count(), errors.keepLimit)
})

Deno.test("missing permissions are pulled out of the error", () => {
  isolate(errors.db)
  errors.record(new BotMissingPermissions(["AttachFiles", "EmbedLinks"]), {
    source: "slash command",
    command: "pride",
  })

  assertEquals(errors.recent()[0].missing, ["AttachFiles", "EmbedLinks"])
})

Deno.test("a fault reads as a code and a digest", () => {
  isolate(errors.db)
  const { ref } = logged(boom(), { source: "event messageCreate" })
  const [code, digest] = ref.split("-")

  assert(code in errors.codeMeanings)
  assertEquals(digest.length, errors.refLength)
  for (const character of digest) {
    assertStringIncludes(errors.refAlphabet, character)
    assert(!"ILOU".includes(character))
  }
})

Deno.test("the same fault twice keeps one reference and counts up", () => {
  isolate(errors.db)
  const make = () => boom()
  const first = logged(make(), { source: "slash command", command: "qr" })
  const second = logged(make(), { source: "slash command", command: "qr" })

  assertEquals(second.ref, first.ref)
  assertEquals(errors.count(), 1)
  assertEquals(second.count, 2)
  assertEquals(second.first, first.first)
})

Deno.test("same fault in another command gets its own reference", () => {
  isolate(errors.db)
  const make = () => boom()
  const first = logged(make(), { source: "slash command", command: "qr" })
  const other = logged(make(), {
    source: "slash command",
    command: "pride",
  })

  assertNotEquals(other.ref, first.ref)
  assertEquals(errors.count(), 2)
})

Deno.test("ids in the message do not split one fault into many", () => {
  isolate(errors.db)
  const make = (id: string) => boom(`member ${id} is gone`)
  const mine = logged(make("777888999000111222"), { source: "command" })
  const yours = logged(make("111222333444555666"), { source: "command" })

  assertEquals(yours.ref, mine.ref)
  assertEquals(yours.count, 2)
})

Deno.test("a quoted fault is found however it was typed", () => {
  isolate(errors.db)
  const { ref } = logged(boom(), { source: "event messageCreate" })
  const [code, digest] = ref.split("-")

  const typings = [
    ref,
    ref.toLowerCase(),
    `\`${ref}\``,
    `#${ref}`,
    `  ${ref} `,
    ref.replace("-", " "),
    ref.replace("-", "—"),
    digest,
    code,
  ]
  for (const typed of typings) {
    assert(errors.find(typed) !== null, typed)
  }

  assertEquals(errors.find("ZZZZ"), null)
  assertEquals(errors.find(""), null)
})

Deno.test("the note carries the reference to whoever hit the error", () => {
  isolate(errors.db)
  const entry = logged(boom(), { source: "slash command", command: "qr" })

  assertStringIncludes(errors.note(entry), entry.ref)
  assertEquals(errors.note(null), "")
})

Deno.test("a missing permission is a workshop fault", () => {
  isolate(errors.db)
  const entry = logged(new BotMissingPermissions(["AttachFiles"]), {
    source: "slash command",
    command: "qr",
  })

  assertEquals(entry.code, "WORKSHOP")
  assert(entry.ref.startsWith("WORKSHOP-"))
})

Deno.test("discord refusing is told apart from discord breaking", () => {
  assertEquals(codeFor(discordError(403)), "WORKSHOP")
  assertEquals(codeFor(discordError(404)), "VANISHED")
  assertEquals(codeFor(discordError(500)), "STRINGS")
})

Deno.test("the outside world and the disk get their own codes", () => {
  assertEquals(codeFor(new UpstreamError("bad gateway", 502)), "BLIZZARD")
  assertEquals(
    codeFor(new TypeError("error sending request for url")),
    "BLIZZARD",
  )
  assertEquals(
    codeFor(new DOMException("slow", "TimeoutError")),
    "BLIZZARD",
  )
  assertEquals(codeFor(new Deno.errors.NotFound("no file")), "FOUNDRY")
  assertEquals(codeFor(new SyntaxError("bad JSON")), "BLUEPRINT")
  assertEquals(
    codeFor(new TypeError("Cannot read properties of undefined")),
    "BLUEPRINT",
  )
})

Deno.test("an unknown fault depends on whether a command was running", () => {
  assertEquals(errors.codeOf(boom(), "slash command"), errors.fallbackCode)
  assertEquals(
    errors.codeOf(boom(), "event messageCreate"),
    errors.loneWorkCode,
  )
  assertEquals(errors.codeOf(boom(), "incident loop"), errors.loneWorkCode)
})

Deno.test("every code that can be issued has a meaning", () => {
  const issuable = new Set([
    ...errors.codes.map(([name]) => name),
    errors.fallbackCode,
    errors.loneWorkCode,
  ])
  assertEquals(issuable, new Set(Object.keys(errors.codeMeanings)))
})

Deno.test("faults can be pulled out by their code", () => {
  isolate(errors.db)
  logged(new BotMissingPermissions(["EmbedLinks"]), {
    source: "command",
    command: "a",
  })
  logged(boom(), { source: "slash command", command: "b" })

  assertEquals(errors.byCode("workshop").map((entry) => entry.code), [
    "WORKSHOP",
  ])
  assertEquals(errors.byCode("BLIZZARD"), [])
})

Deno.test("recording never throws, even when the log itself breaks", () => {
  isolate(errors.db)
  const original = errors.db.save
  errors.db.save = () => {
    throw new Error("disk is on fire")
  }
  try {
    assertEquals(errors.record(boom(), { source: "event" }), null)
  } finally {
    errors.db.save = original
  }
})
