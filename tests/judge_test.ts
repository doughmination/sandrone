/* tests/judge_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assertEquals } from "@std/assert"
import { config } from "../src/config.ts"
import * as mood from "../src/mood.ts"
import { PyRandom } from "../src/utils/pyrandom.ts"
import { patch } from "./_helpers.ts"

// Expected values were taken from CPython 3's random.Random
Deno.test("PyRandom matches CPython's Mersenne Twister", () => {
  const cases: Array<[bigint, number, number]> = [
    [0n, 3626764237, 1654615998],
    [42n, 2746317213, 478163327],
    [1025770042245251122n, 2201953297, 93211520],
    [2n ** 64n + 5n, 2192917427, 3085273184],
  ]
  for (const [seed, first, second] of cases) {
    const random = new PyRandom(seed)
    assertEquals(random.getRandBits(32), first)
    assertEquals(random.getRandBits(32), second)
  }
})

Deno.test("PyRandom.choice picks what CPython picks", () => {
  const range = (size: number) => Array.from({ length: size }, (_, i) => i)
  assertEquals(new PyRandom(777888999000111222n).choice(range(55)), 27)
  assertEquals(new PyRandom(42n).choice(range(1000)), 654)
})

Deno.test("a user always gets the same verdict", () => {
  const user = {
    id: "777888999000111222",
  }
  assertEquals(mood.judge(user), mood.judge(user))
})

Deno.test("special users get their fixed line", () => {
  assertEquals(
    mood.judge({ id: "1025770042245251122" }),
    "Sandrone chooses not to comment on her creator.",
  )
})

Deno.test("Sandrone judges herself kindly", () => {
  const restore = patch(config, { clientId: "123456789012345678" })
  try {
    assertEquals(
      mood.judge({ id: "123456789012345678" }),
      "Sandrone thinks she is the best person ever",
    )
  } finally {
    restore()
  }
})
