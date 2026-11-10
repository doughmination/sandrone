/* tests/choices_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assertEquals } from "@std/assert"
import { ChoiceSet, spellings } from "../src/utils/choices.ts"

const containers = new ChoiceSet({
  Audio: "mp3",
  Video: "mp4",
})

const indents = new ChoiceSet({
  "2 spaces": "2",
  Tab: "tab",
})

Deno.test("spellings cover the value and the label", () => {
  assertEquals(spellings("Audio", "mp3"), new Set(["audio", "mp3"]))
})

Deno.test("spellings cover punctuated forms of a two word label", () => {
  assertEquals(
    spellings("Caesar Cipher", "caesar"),
    new Set([
      "caesar",
      "caesar cipher",
      "caesarcipher",
      "caesar-cipher",
      "caesar_cipher",
    ]),
  )
})

Deno.test("the slash menu only ever sees labels and values", () => {
  assertEquals(containers.options, [
    { name: "Audio", value: "mp3" },
    { name: "Video", value: "mp4" },
  ])
})

Deno.test("resolve falls back to the default for nothing supplied", () => {
  assertEquals(containers.resolve(null, "mp4"), "mp4")
})

Deno.test("resolve normalises a label that reached it unconverted", () => {
  assertEquals(containers.resolve("Audio", "mp4"), "mp3")
})

Deno.test("resolve uses the default rather than inventing a value", () => {
  assertEquals(containers.resolve("nonsense", "mp4"), "mp4")
})

Deno.test("a label whose spelling needs quoting still resolves", () => {
  assertEquals(indents.resolve("2 spaces", "2"), "2")
  assertEquals(indents.resolve("2spaces", "2"), "2")
})
