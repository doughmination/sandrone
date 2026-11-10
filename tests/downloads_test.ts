/* tests/downloads_test.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { assert, assertEquals } from "@std/assert"
import { basename, join } from "@std/path"
import { config } from "../src/config.ts"
import * as downloads from "../src/utils/downloads.ts"
import { patch, tempDir } from "./_helpers.ts"

function exists(path: string): boolean {
  try {
    Deno.statSync(path)
    return true
  } catch {
    return false
  }
}

function age(path: string, hours: number): void {
  const old = new Date(Date.now() - hours * 3_600_000)
  Deno.utimeSync(path, old, old)
}

// Each test gets its own downloads folder and a one-hour retention
function withDownloadRoot(test: (root: string) => void): () => void {
  return () => {
    const root = tempDir()
    const restore = patch(config, {
      downloadsDir: root,
      downloadsRetentionHours: 1,
    })
    try {
      test(root)
    } finally {
      restore()
    }
  }
}

function slotWithVideo(): string {
  const slot = downloads.newSlot()
  Deno.writeTextFileSync(join(slot, "video.mp4"), "video")
  return slot
}

Deno.test(
  "purge only removes managed slots",
  withDownloadRoot((root) => {
    const slot = slotWithVideo()
    downloads.recordSource(slot, "key", "video.mp4", {
      title: "Video",
      size: 5,
    })

    const unrelatedDirectory = join(root, "source")
    Deno.mkdirSync(unrelatedDirectory)
    const unrelatedFile = join(root, "notes.txt")
    Deno.writeTextFileSync(unrelatedFile, "keep me")

    for (const path of [slot, unrelatedDirectory, unrelatedFile]) {
      age(path, 2)
    }

    assertEquals(downloads.purgeExpired(), 1)
    assertEquals(exists(slot), false)
    assert(exists(unrelatedDirectory))
    assert(exists(unrelatedFile))
  }),
)

Deno.test(
  "discard ignores unmanaged directories",
  withDownloadRoot((root) => {
    const directory = join(root, "important")
    Deno.mkdirSync(directory)

    downloads.discard(directory)

    assert(exists(directory))
  }),
)

Deno.test(
  "reserved metadata cannot be overridden",
  withDownloadRoot(() => {
    const slot = downloads.newSlot()
    downloads.recordSource(slot, "expected-key", "video.mp4", {
      key: "other",
      name: "other.mp4",
      title: "Video",
    })

    const data = JSON.parse(
      Deno.readTextFileSync(join(slot, downloads.metaName)),
    )
    assertEquals(data.key, "expected-key")
    assertEquals(data.name, "video.mp4")
  }),
)

const invalidMetadata: Record<string, unknown> = {
  "not an object": [],
  "missing title": {
    key: "key",
    name: "video.mp4",
    size: 5,
  },
  "missing size": {
    key: "key",
    name: "video.mp4",
    title: "Video",
  },
  "invalid size": {
    key: "key",
    name: "video.mp4",
    title: "Video",
    size: "5",
  },
  "invalid title": {
    key: "key",
    name: "video.mp4",
    title: 123,
    size: 5,
  },
  "boolean size": {
    key: "key",
    name: "video.mp4",
    title: "Video",
    size: true,
  },
}

for (const [label, metadata] of Object.entries(invalidMetadata)) {
  Deno.test(
    `invalid cache metadata is ignored: ${label}`,
    withDownloadRoot(() => {
      const slot = slotWithVideo()
      Deno.writeTextFileSync(
        join(slot, downloads.metaName),
        JSON.stringify(metadata),
      )

      assertEquals(downloads.findCached("key"), null)
    }),
  )
}

Deno.test(
  "valid cache metadata is returned",
  withDownloadRoot(() => {
    const slot = slotWithVideo()
    downloads.recordSource(slot, "key", "video.mp4", {
      title: "Video",
      size: 5,
    })

    const cached = downloads.findCached("key")

    assert(cached !== null)
    assertEquals(cached.title, "Video")
    assertEquals(cached.size, 5)
  }),
)

Deno.test(
  "an expired download is not handed out again",
  withDownloadRoot(() => {
    const slot = slotWithVideo()
    downloads.recordSource(slot, "key", "video.mp4", {
      title: "Video",
      size: 5,
    })
    age(slot, 2)

    assertEquals(downloads.findCached("key"), null)
  }),
)

Deno.test(
  "public url uses the download prefix",
  withDownloadRoot(() => {
    const restore = patch(config, {
      downloadsUrl: "https://sandrone.example",
    })
    try {
      const slot = downloads.newSlot()
      assertEquals(
        downloads.publicUrl(slot, "video file.mp4"),
        `https://sandrone.example/d/${basename(slot)}/video%20file.mp4`,
      )
    } finally {
      restore()
    }
  }),
)

Deno.test("names that could escape the slot are refused", () => {
  for (
    const name of ["", ".", "..", ".meta.json", "a/b", "a\\b", "a\nb"]
  ) {
    assertEquals(downloads.validName(name), false, JSON.stringify(name))
  }
  assertEquals(downloads.validName("video.mp4"), true)
})
