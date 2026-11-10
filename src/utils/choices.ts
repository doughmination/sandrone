/* src/utils/choices.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import type { APIApplicationCommandOptionChoice } from "discord.js"

export function spellings(label: string, value: string): Set<string> {
  const lowered = label.toLowerCase()
  const forms = [
    value.toLowerCase(),
    lowered,
    lowered.replaceAll(" ", ""),
    lowered.replaceAll(" ", "-"),
    lowered.replaceAll(" ", "_"),
  ]
  return new Set(forms.filter(Boolean))
}

export class ChoiceSet {
  readonly values: string[]
  readonly table: Map<string, string>

  constructor(readonly choices: Record<string, string>) {
    this.values = [...new Set(Object.values(choices))]

    this.table = new Map()
    for (const [label, value] of Object.entries(choices)) {
      for (const form of spellings(label, value)) {
        if (!this.table.has(form)) {
          this.table.set(form, value)
        }
      }
    }
  }

  get options(): APIApplicationCommandOptionChoice<string>[] {
    return Object.entries(this.choices).map(([label, value]) => ({
      name: label,
      value,
    }))
  }

  resolve(typed: string | null | undefined, fallback: string): string {
    if (typed === null || typed === undefined) {
      return fallback
    }
    return this.table.get(typed.toLowerCase()) ?? fallback
  }
}
