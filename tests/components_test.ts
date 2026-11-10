/* tests/components_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assert, assertEquals, assertStringIncludes } from "@std/assert"
import { ComponentType, MessageFlags } from "discord.js"
import * as components from "../src/utils/components.ts"

interface Json {
  type: number
  // deno-lint-ignore no-explicit-any
  [key: string]: any
}

function children(box: ReturnType<typeof components.container>): Json[] {
  return box.toJSON().components as Json[]
}

function textOf(blocks: Json[]): string {
  return blocks
    .flatMap((block) =>
      block.type === ComponentType.Section ? block.components : [block]
    )
    .filter((block: Json) => block.type === ComponentType.TextDisplay)
    .map((block: Json) => block.content)
    .join("")
}

Deno.test("panel wraps a single container as a components v2 message", () => {
  const message = components.panel({ title: "Hello", body: "world" })

  assertEquals(message.components.length, 1)
  assertEquals(message.flags, MessageFlags.IsComponentsV2)
})

Deno.test("container lays out every piece", () => {
  const box = components.container({
    title: "Title",
    url: "https://example.com",
    body: "Body text",
    fields: [["One", "1"], ["Two", "2"]],
    thumbnail: "https://example.com/thumb.png",
    images: ["https://example.com/a.png", "https://example.com/b.png"],
    footer: "Sandrone",
    color: components.FUCHSIA,
  })

  const blocks = children(box)
  const kinds = blocks.map((block) => block.type)
  assert(kinds.includes(ComponentType.Section))
  assert(kinds.includes(ComponentType.MediaGallery))
  assert(kinds.includes(ComponentType.Separator))
  assertEquals(box.toJSON().accent_color, components.FUCHSIA)
  assertStringIncludes(textOf(blocks), "## [Title](https://example.com)")
})

Deno.test("error uses the red accent", () => {
  const box = components.error("nope").components[0]

  assertEquals(box.toJSON().accent_color, components.RED)
  assertStringIncludes(textOf(children(box)), ":x: nope")
})

Deno.test("buttons render as a row inside the container", () => {
  const box = components.container({
    body: "pick one",
    buttons: [
      components.linkButton("A", "https://example.com/a"),
      components.linkButton("B", "https://example.com/b", "🔗"),
    ],
    footer: "f",
  })

  const rows = children(box).filter(
    (block) => block.type === ComponentType.ActionRow,
  )
  assertEquals(rows.length, 1)
  const buttons = rows[0].components as Json[]
  assertEquals(buttons.map((button) => button.label), ["A", "B"])
  assert(buttons.every((button) => typeof button.url === "string"))
})

Deno.test("gallery accepts urls and image items and caps at ten", () => {
  const box = components.container({
    images: [
      "https://example.com/0.png",
      components.image("https://example.com/1.png", { alt: "one" }),
      ...Array.from(
        { length: 18 },
        (_, index) => `https://example.com/${index + 2}.png`,
      ),
    ],
  })

  const galleries = children(box).filter(
    (block) => block.type === ComponentType.MediaGallery,
  )
  assertEquals(galleries.length, 1)
  assertEquals(galleries[0].items.length, 10)
  assertEquals(galleries[0].items[1].description, "one")
})

Deno.test("container renders without any pieces", () => {
  assertEquals(children(components.container()).length, 1)
})

Deno.test("ephemeral keeps the components v2 flag", () => {
  const message = components.ephemeral(components.panel({ body: "hi" }))

  assert(message.flags & MessageFlags.IsComponentsV2)
  assert(message.flags & MessageFlags.Ephemeral)
})

Deno.test("code blocks can't be broken out of", () => {
  assertEquals(
    components.codeBlock("a```b", "py"),
    "```py\na`​``b\n```",
  )
})

Deno.test("caret points at the column on the right line", () => {
  assertEquals(components.caretAt("one\ntwo", 5), "two\n ^")
  assertEquals(components.caretAt("\nx", 0), "\n^")
})

Deno.test("numbered lines can't turn into a markdown list", () => {
  assertEquals(components.escapeMarkdown("1. hi"), "1\\. hi")
})
