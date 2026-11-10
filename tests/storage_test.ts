/* tests/storage_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assertEquals, assertStringIncludes } from "@std/assert"
import { join } from "@std/path"
import { DataBase } from "../src/utils/storage.ts"
import { tempDir } from "./_helpers.ts"

function freshDb(): DataBase {
  const db = new DataBase("sample", 1)
  db.path = join(tempDir(), "sample.jp")
  db.reload()
  return db
}

Deno.test("a file written by the Python bot reads back unchanged", () => {
  const db = freshDb()
  Deno.writeTextFileSync(
    db.path,
    [
      "version: 1",
      "",
      "[1234567890]",
      "roles: [111222333444555666]",
      "users: [777888999000111222]",
      "",
      "[9876543210]",
      "roles: [222333444555666777]",
      "users:",
      "",
    ].join("\n"),
  )
  db.reload()

  assertEquals(db.sections(), ["1234567890", "9876543210"])
  assertEquals(db.guild("1234567890").key("roles").ids(), [
    "111222333444555666",
  ])
  assertEquals(db.guild("9876543210").key("users").ids(), [])
})

Deno.test("snowflakes are written back as bare integers", () => {
  const db = freshDb()
  db.guild("1").key("users").addIds("777888999000111222").save()

  const written = Deno.readTextFileSync(db.path)
  assertStringIncludes(written, "users: [777888999000111222]")
  assertStringIncludes(written, "version: 1")
})

Deno.test("id lists stay sorted and never hold a duplicate", () => {
  const db = freshDb()
  const field = db.guild("1").key("users")
  field.addIds("300000000000000003", "100000000000000001")
  field.addIds("100000000000000001", "200000000000000002")

  assertEquals(field.ids(), [
    "100000000000000001",
    "200000000000000002",
    "300000000000000003",
  ])
  assertEquals(field.hasId("200000000000000002"), true)
})

Deno.test("removing the last id drops the key entirely", () => {
  const db = freshDb()
  const field = db.guild("1").key("users")
  field.addIds("100000000000000001")
  field.removeIds("100000000000000001")

  assertEquals(field.exists(), false)
})

Deno.test("a clean database is never rewritten", () => {
  const db = freshDb()
  db.open()
  db.save()

  let exists = true
  try {
    Deno.statSync(db.path)
  } catch {
    exists = false
  }
  assertEquals(exists, false)
})

Deno.test("reading a missing section never creates it", () => {
  const db = freshDb()
  assertEquals(db.guild("42").key("anything").read("fallback"), "fallback")
  assertEquals(db.has("42"), false)
  assertEquals(db.dirty, false)
})

Deno.test("clearing a section removes it from the file", () => {
  const db = freshDb()
  db.guild("1").key("a").write(1)
  db.guild("2").key("b").write(2)
  db.guild("1").clear().save()
  db.reload()

  assertEquals(db.sections(), ["2"])
})
