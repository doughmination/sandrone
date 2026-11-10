/* src/utils/components.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  ContainerBuilder,
  escapeMarkdown as discordEscape,
  FileBuilder,
  MediaGalleryBuilder,
  MediaGalleryItemBuilder,
  MessageFlags,
  SectionBuilder,
  SeparatorBuilder,
  StringSelectMenuBuilder,
  TextDisplayBuilder,
  ThumbnailBuilder,
} from "discord.js"

// discord.py's Color.fuchsia(), .red(), .gold() and .dark_teal()
export const FUCHSIA = 0xEB459E
export const RED = 0xE74C3C
export const GOLD = 0xF1C40F
export const DARK_TEAL = 0x11806A

const blank = "​"

export type Field = readonly [name: string, value: string]
export type Media = string | MediaGalleryItemBuilder

// key, label, description
export type PageOption = readonly [
  key: string,
  label: string,
  description: string | null,
]

export interface Panel {
  components: ContainerBuilder[]
  flags: number
}

export interface PanelOptions {
  title?: string | null
  url?: string | null
  body?: string | null
  fields?: Field[] | null
  thumbnail?: string | null
  images?: Media[] | null
  files?: string[] | null
  menu?: StringSelectMenuBuilder | null
  buttons?: ButtonBuilder[] | null
  footer?: string | null
  color?: number | null
}

export function image(
  url: string,
  options: { alt?: string | null; spoiler?: boolean } = {},
): MediaGalleryItemBuilder {
  const item = new MediaGalleryItemBuilder().setURL(url)
  if (options.alt) {
    item.setDescription(options.alt)
  }
  if (options.spoiler) {
    item.setSpoiler(true)
  }
  return item
}

export function heading(title: string, url?: string | null): string {
  return url ? `## [${title}](${url})` : `## ${title}`
}

export function renderFields(fields: Field[]): string {
  return fields
    .map(([name, value]) => `**${name}**\n${value}`)
    .join("\n\n")
}

export function text(content: string): TextDisplayBuilder {
  return new TextDisplayBuilder().setContent(content)
}

export function linkButton(
  label: string,
  url: string,
  emoji?: string | null,
): ButtonBuilder {
  const button = new ButtonBuilder()
    .setLabel(label)
    .setURL(url)
    .setStyle(ButtonStyle.Link)
  if (emoji) {
    button.setEmoji(emoji)
  }
  return button
}

export function pagePicker(
  customId: string,
  pages: PageOption[],
  current: string,
  placeholder = "Jump to a section…",
): StringSelectMenuBuilder {
  const options = pages.slice(0, 25).map(([key, label, description]) => {
    const option = {
      label: label.slice(0, 100),
      value: key,
      default: key === current,
    }
    return description
      ? {
        ...option,
        description: description.slice(0, 100),
      }
      : option
  })
  return new StringSelectMenuBuilder()
    .setCustomId(customId)
    .setPlaceholder(placeholder)
    .addOptions(options)
}

export function container(options: PanelOptions = {}): ContainerBuilder {
  const {
    title,
    url,
    body,
    fields,
    thumbnail,
    images,
    files,
    menu,
    buttons,
    footer,
    color = FUCHSIA,
  } = options

  const box = new ContainerBuilder()
  if (color !== null && color !== undefined) {
    box.setAccentColor(color)
  }

  const lead = [title ? heading(title, url) : null, body]
    .filter(Boolean)
    .join("\n\n")
  let isEmpty = true

  if (thumbnail) {
    box.addSectionComponents(
      new SectionBuilder()
        .addTextDisplayComponents(text(lead || blank))
        .setThumbnailAccessory(new ThumbnailBuilder().setURL(thumbnail)),
    )
    isEmpty = false
  } else if (lead) {
    box.addTextDisplayComponents(text(lead))
    isEmpty = false
  }

  if (fields?.length) {
    box.addTextDisplayComponents(text(renderFields(fields)))
    isEmpty = false
  }

  if (images?.length) {
    const items = images
      .slice(0, 10)
      .map((item) => typeof item === "string" ? image(item) : item)
    box.addMediaGalleryComponents(
      new MediaGalleryBuilder().addItems(...items),
    )
    isEmpty = false
  }

  for (const ref of files ?? []) {
    box.addFileComponents(new FileBuilder().setURL(ref))
    isEmpty = false
  }

  if (menu) {
    box.addActionRowComponents(
      new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu),
    )
    isEmpty = false
  }

  if (buttons?.length) {
    box.addActionRowComponents(
      new ActionRowBuilder<ButtonBuilder>().addComponents(...buttons),
    )
    isEmpty = false
  }

  if (footer) {
    box.addSeparatorComponents(new SeparatorBuilder().setDivider(false))
    box.addTextDisplayComponents(text(`-# ${footer}`))
    isEmpty = false
  }

  if (isEmpty) {
    box.addTextDisplayComponents(text(blank))
  }

  return box
}

export function wrap(box: ContainerBuilder): Panel {
  return {
    components: [box],
    flags: MessageFlags.IsComponentsV2,
  }
}

export function panel(options: PanelOptions = {}): Panel {
  return wrap(container(options))
}

export function error(message: string): Panel {
  return panel({
    body: `:x: ${message}`,
    color: RED,
  })
}

// Only the person who ran the command sees it
export function ephemeral<T extends { flags: number }>(message: T): T {
  return {
    ...message,
    flags: message.flags | MessageFlags.Ephemeral,
  }
}

const orderedListPrefix = /^(\s*\d+)(?=\.\s)/gm

export function escapeMarkdown(value: string): string {
  return discordEscape(value).replace(orderedListPrefix, "$1\\")
}

export function codeBlock(value: string, language = ""): string {
  return `\`\`\`${language}\n${value.replaceAll("```", "`​``")}\n\`\`\``
}

export function caretAt(
  value: string,
  position: number,
  window = 60,
): string {
  const previousBreak = position > 0
    ? value.lastIndexOf("\n", position - 1)
    : -1
  const lineStart = previousBreak + 1
  let lineEnd = value.indexOf("\n", position)
  if (lineEnd === -1) {
    lineEnd = value.length
  }

  const line = value.slice(lineStart, lineEnd)
  const column = position - lineStart
  const start = Math.max(0, column - window)
  const end = Math.min(line.length, column + window)

  const prefix = start > 0 ? "…" : ""
  const suffix = end < line.length ? "…" : ""
  const caret = " ".repeat(prefix.length + column - start) + "^"
  return `${prefix}${line.slice(start, end)}${suffix}\n${caret}`
}
