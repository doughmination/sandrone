/* src/main.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import { runBot } from "./client.ts"
import { config } from "./config.ts"

if (import.meta.main) {
  if (!config.token) {
    console.error("The Bot Token is not set, please configure .env")
    Deno.exit(1)
  }
  await runBot()
}
