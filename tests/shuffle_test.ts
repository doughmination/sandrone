/* tests/shuffle_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assertEquals, assertNotEquals } from "@std/assert"
import * as mood from "../src/mood.ts"
import { isolate } from "./_helpers.ts"

const items = [
  "a",
  "b",
  "c",
  "d",
]

function sorted(values: string[]): string[] {
  return [...values].sort()
}

function drawMany(
  bag: mood.ShuffleBag,
  guild: string | null,
  times: number,
) {
  return Array.from({ length: times }, () => bag.draw(guild))
}

Deno.test("every item comes out once before any repeat", () => {
  isolate(mood.bagDb)
  const bag = new mood.ShuffleBag("test", items)
  assertEquals(sorted(drawMany(bag, "1", items.length)), items)
})

Deno.test("each guild has its own bag", () => {
  isolate(mood.bagDb)
  const bag = new mood.ShuffleBag("test", items)
  const first = drawMany(bag, "1", 2)
  // Guild 2 drawing in between must not eat into guild 1's bag
  const other = drawMany(bag, "2", items.length)
  const rest = drawMany(bag, "1", 2)

  assertEquals(sorted([...first, ...rest]), items)
  assertEquals(sorted(other), items)
})

Deno.test("no repeat straight across a refill", () => {
  isolate(mood.bagDb)
  const bag = new mood.ShuffleBag("test", items)
  let previous: string | null = null
  for (let round = 0; round < 200; round++) {
    const drawn = bag.draw("1")
    assertNotEquals(drawn, previous)
    previous = drawn
  }
})

Deno.test("the bag survives a reload", () => {
  isolate(mood.bagDb)
  const bag = new mood.ShuffleBag("test", items)
  const first = drawMany(bag, "1", 2)
  mood.bagDb.save()
  mood.bagDb.reload()
  const rest = drawMany(bag, "1", 2)

  assertEquals(sorted([...first, ...rest]), items)
})

Deno.test("lines edited out are dropped from the bag", () => {
  isolate(mood.bagDb)
  new mood.ShuffleBag("test", items).draw("1")
  const bag = new mood.ShuffleBag("test", ["a", "z"])

  assertEquals(new Set(drawMany(bag, "1", 2)), new Set(["a", "z"]))
})

Deno.test("dms share one bag", () => {
  isolate(mood.bagDb)
  const bag = new mood.ShuffleBag("test", items)
  assertEquals(sorted(drawMany(bag, null, items.length)), items)
})
