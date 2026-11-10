/* src/mood.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import type { ChatInputCommandInteraction } from "discord.js"
import { config } from "./config.ts"
import * as components from "./utils/components.ts"
import { SassyDenial } from "./utils/failures.ts"
import { PyRandom } from "./utils/pyrandom.ts"
import { database, type Scope } from "./utils/storage.ts"

export const sassyChance = 20

export const bagDb = database("shuffle", { version: 1 })

// Where draws outside a guild (DMs) keep their bag
export const noGuildSection = "dm"

function shuffled<T>(items: readonly T[]): T[] {
  const copy = [...items]
  for (let index = copy.length - 1; index > 0; index--) {
    const swap = Math.floor(Math.random() * (index + 1))
    ;[copy[index], copy[swap]] = [copy[swap], copy[index]]
  }
  return copy
}

// Hands out every item once, in random order, before any repeat
export class ShuffleBag {
  constructor(
    readonly name: string,
    readonly items: readonly string[],
  ) {}

  private scope(guildId: string | null): Scope {
    return guildId === null
      ? bagDb.section(noGuildSection)
      : bagDb.guild(guildId)
  }

  draw(guildId: string | null): string {
    const scope = this.scope(guildId)
    const remainingField = scope.key(`${this.name}_remaining`)
    const lastField = scope.key(`${this.name}_last`)

    // Lines edited out since the bag was filled can't come back
    const known = new Set(this.items)
    let remaining = remainingField
      .list()
      .filter((item): item is string => known.has(item as string))
    const last = lastField.read<string>()

    if (!remaining.length) {
      remaining = shuffled(this.items)
      // Don't repeat the last line straight across a refill
      if (remaining.length > 1 && remaining.at(-1) === last) {
        const final = remaining.length - 1
        ;[remaining[0], remaining[final]] = [
          remaining[final],
          remaining[0],
        ]
      }
    }

    const drawn = remaining.pop() as string
    remainingField.write(remaining)
    lastField.write(drawn)
    return drawn
  }
}

export const sassyReplies = [
  "Sandrone has determined that this command is beneath her.",
  "Sandrone is tired of your command usage. Ask again nicely and she " +
  "might do it.",
  "Sandrone has decided that you have used enough commands today.",
  "The puppet has reviewed your request. It has declined.",
  "Your command has been rejected on the grounds that Sandrone doesn't " +
  "feel like it.",
]

export const sassyBag = new ShuffleBag("sassy", sassyReplies)

// One in sassyChance commands is refused, with a reply
export async function sassyCheck(
  interaction: ChatInputCommandInteraction,
): Promise<void> {
  if (Math.floor(Math.random() * sassyChance) !== 0) {
    return
  }

  await interaction.reply(
    components.panel({
      body: "<:sandrone_refuses:1546669792595939468> " +
        sassyBag.draw(interaction.guildId),
      color: components.GOLD,
    }),
  )
  throw new SassyDenial()
}

export const judgeCertainUser: Record<string, string> = {
  "1025770042245251122": "Sandrone chooses not to comment on her creator.",
  "1542295080524845148":
    "The puppet decided that the real Sandrone is much nicer.",
}

export const judgeReplies = [
  "Sandrone has reviewed the evidence. She is unconvinced.",
  "The puppet has observed this individual. Further investigation is " +
  "recommended.",
  "Verdict: suspicious.",
  "Sandrone has decided that this person is probably fine. Probably.",
  "The puppet finds them tolerable.",
  "Verdict: acceptable. Do not get excited.",
  "Sandrone has no objections at this time.",
  "The puppet has reviewed the subject and would like to keep them at a " +
  "safe distance.",
  "Verdict: mildly concerning.",
  "Sandrone has determined that this individual requires supervision.",
  "The puppet approves. She doesn't know why.",
  "Sandrone has reached a verdict. Unfortunately, it is complicated.",
  "Verdict: guilty of being annoying.",
  "Sandrone has found insufficient evidence to justify throwing them " +
  "out of the workshop.",
  "The puppet has considered the matter carefully. The answer is 'eh.'",
  "Verdict: suspiciously competent.",
  "Sandrone has determined that this person may remain. For now.",
  "The puppet has no comment. This is somehow worse than a comment.",
  "Verdict: needs further testing.",
  "Sandrone has inspected the subject. The results are inconclusive.",
  "The puppet says they are fine. The puppet is not a qualified judge.",
  "Verdict: surprisingly tolerable.",
  "Sandrone has decided that this person is not worth the paperwork.",
  "The puppet has filed them under 'probably harmless.'",
  "Verdict: workshop access denied.",
  "Sandrone has determined that this individual has potential. Whether " +
  "that is good or bad remains unclear.",
  "The puppet has seen enough. Judgment rendered.",
  "Verdict: guilty of something. Sandrone will determine what later.",
  "Sandrone has decided to give them the benefit of the doubt. She " +
  "already regrets it.",
  "The puppet has reviewed their behaviour and would like to speak to " +
  "their manager.",
  "Verdict: questionable.",
  "Sandrone sees no reason to panic. Yet.",
  "The puppet has classified this person as 'interesting.' This is not " +
  "necessarily a compliment.",
  "Verdict: acceptable specimen.",
  "Sandrone has determined that they may continue existing.",
  "The puppet has reviewed the subject and recommends keeping all " +
  "valuable tools locked away.",
  "Verdict: too powerful. Keep an eye on them.",
  "Sandrone has decided that this person is allowed within five metres " +
  "of the workshop.",
  "The puppet has reached a conclusion. Nobody asked what it was.",
  "Verdict: Sandrone will tolerate them.",
  "Sandrone has determined that this person is either a genius or a " +
  "complete idiot.",
  "The puppet cannot tell which. Further testing required.",
  "Verdict: unexpectedly based.",
  "Sandrone has judged this person. The court is adjourned.",
  "The puppet has spoken. You probably shouldn't ask what it said.",
  "Verdict: needs more data.",
  "Sandrone has determined that this individual is harmless. The puppet " +
  "disagrees.",
  "The puppet has awarded them one point. Nobody knows what the points " +
  "are for.",
  "Verdict: tolerable. Barely.",
]

// Seeded by user id the same way Python's random.Random was
export function judge(user: { id: string }): string {
  const certain = judgeCertainUser[user.id]
  if (certain !== undefined) {
    return certain
  }
  if (user.id === config.clientId) {
    return "Sandrone thinks she is the best person ever"
  }
  return new PyRandom(BigInt(user.id)).choice(judgeReplies)
}

export const incidentReplies = [
  "The puppet has escaped the workshop.",
  "The puppet has discovered doors.",
  "Sandrone has misplaced her screwdriver. She suspects everyone.",
  "The puppet is carrying a chair. It refuses to explain itself.",
  "The puppet has learned a new word. Sandrone will not say which.",
  "Something in the workshop is ticking. Sandrone did not build " +
  "anything that ticks.",
  "The puppet has been standing in the corner for six hours. This is " +
  "fine.",
  "Sandrone has counted her tools. There are more than there should be.",
  "The puppet found the vents. Nobody tell it where they lead.",
  "A drawer that was locked is now open. Sandrone is choosing not to " +
  "investigate.",
  "The puppet has assembled something. It has too many legs.",
  "Sandrone left the room for one minute. The furniture has been " +
  "rearranged.",
  "The puppet is watching the ceiling. The ceiling has not moved. Yet.",
  "Sandrone has found a screw on the floor. She does not know what it " +
  "came from. This is concerning.",
  "The puppet has started collecting spoons. Nobody has questioned this " +
  "out loud.",
  "There is a second puppet now. Sandrone is aware. It is being handled.",
  "The puppet has climbed onto the workbench and will not come down.",
  "Sandrone's blueprints have been reorganised by colour. She did not " +
  "do this.",
  "The puppet has been humming the same three notes since this morning.",
  "A tool is missing. The puppet is making direct eye contact. Sandrone " +
  "has drawn her own conclusions.",
]

export const incidentBag = new ShuffleBag("incident", incidentReplies)

export function randomIncident(guildId: string | null): string {
  return incidentBag.draw(guildId)
}
