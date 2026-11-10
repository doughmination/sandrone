/* tests/cooldowns_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assertEquals, assertThrows } from "@std/assert"
import {
  checkCooldown,
  CooldownBucket,
  cooldownOf,
  defaultCooldown,
  resetCooldowns,
} from "../src/checks.ts"
import { config } from "../src/config.ts"
import type { Action } from "../src/framework.ts"
import { CommandOnCooldown } from "../src/utils/failures.ts"

const strangerId = "1"

const plainAction: Action = {
  run() {},
}

Deno.test("a command with no cooldown gets the default", () => {
  assertEquals(cooldownOf(plainAction), defaultCooldown)
})

Deno.test("an explicit cooldown is left alone", () => {
  const action: Action = {
    ...plainAction,
    cooldown: {
      rate: 1,
      per: 60,
    },
  }
  assertEquals(cooldownOf(action), { rate: 1, per: 60 })
})

Deno.test("null turns the cooldown off", () => {
  const action: Action = {
    ...plainAction,
    cooldown: null,
  }
  assertEquals(cooldownOf(action), null)
})

Deno.test("a user is stopped once they run out", () => {
  resetCooldowns()
  const limit = { rate: 2, per: 60 }
  checkCooldown("thing", strangerId, limit, 100)
  checkCooldown("thing", strangerId, limit, 100)
  assertThrows(
    () => checkCooldown("thing", strangerId, limit, 100),
    CommandOnCooldown,
  )
})

Deno.test("the wait shrinks as the window passes, then resets", () => {
  const bucket = new CooldownBucket(1, 60)
  assertEquals(bucket.use(100), null)
  assertEquals(bucket.use(130), 30)
  assertEquals(bucket.use(161), null)
})

Deno.test("users have their own buckets", () => {
  resetCooldowns()
  const limit = { rate: 1, per: 60 }
  checkCooldown("thing", strangerId, limit, 100)
  checkCooldown("thing", "2", limit, 100)
})

Deno.test("commands have their own buckets", () => {
  resetCooldowns()
  const limit = { rate: 1, per: 60 }
  checkCooldown("thing", strangerId, limit, 100)
  checkCooldown("other", strangerId, limit, 100)
})

Deno.test("owners are never held back", () => {
  resetCooldowns()
  const limit = { rate: 1, per: 60 }
  for (let round = 0; round < 5; round++) {
    checkCooldown("thing", config.owners[0], limit, 100)
  }
})
