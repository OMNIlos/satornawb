import { Fragment, createElement } from 'react'
import type { CSSProperties, ReactNode } from 'react'

export type HtmlReactReplacement = {
  selector: string
  render: (key: string, node?: HTMLElement | SVGElement) => ReactNode
}

const attributeNameMap: Record<string, string> = {
  class: 'className',
  for: 'htmlFor',
  readonly: 'readOnly',
  autocomplete: 'autoComplete',
  inputmode: 'inputMode',
  tabindex: 'tabIndex',
  colspan: 'colSpan',
  rowspan: 'rowSpan',
  viewbox: 'viewBox',
  'stroke-width': 'strokeWidth',
  'stroke-dasharray': 'strokeDasharray',
  'stroke-linecap': 'strokeLinecap',
  'stroke-linejoin': 'strokeLinejoin',
  'fill-rule': 'fillRule',
  'clip-rule': 'clipRule',
  'xlink:href': 'xlinkHref',
}

const booleanAttributes = new Set(['disabled', 'hidden', 'readonly', 'checked', 'selected', 'aria-hidden'])

const eventNameMap: Record<string, string> = {
  onblur: 'onBlur',
  onchange: 'onChange',
  onclick: 'onClick',
  ondragleave: 'onDragLeave',
  ondragover: 'onDragOver',
  ondrop: 'onDrop',
  oninput: 'onInput',
  onkeydown: 'onKeyDown',
  onmouseleave: 'onMouseLeave',
  onmousemove: 'onMouseMove',
}

function toReactEventName(attributeName: string) {
  if (eventNameMap[attributeName]) return eventNameMap[attributeName]
  return attributeName.replace(/^on([a-z])/, (_, letter: string) => `on${letter.toUpperCase()}`)
}

function runInlineHandler(code: string, event: unknown) {
  try {
    Function('event', code).call(event && typeof event === 'object' && 'currentTarget' in event
      ? (event as { currentTarget?: EventTarget }).currentTarget
      : undefined, event)
  } catch (error) {
    console.error(`Vella parity inline handler failed: ${code}`, error)
  }
}

export function styleAttributeToObject(styleText: string): CSSProperties {
  return Object.fromEntries(
    styleText
      .split(';')
      .map((item) => item.trim())
      .filter(Boolean)
      .map((declaration) => {
        const [property, ...valueParts] = declaration.split(':')
        const value = valueParts.join(':').trim()
        const camelProperty = property.trim().replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase())
        return [camelProperty, value]
      }),
  ) as CSSProperties
}

function attributeValueToReactValue(name: string, value: string) {
  if (name === 'style') return styleAttributeToObject(value)
  if (booleanAttributes.has(name)) return value === '' || value === name || value === 'true'
  return value
}

export function elementAttributesToProps(element: HTMLElement | SVGElement) {
  const props: Record<string, unknown> = {}
  const convertedHandlers: string[] = []

  for (const attribute of Array.from(element.attributes)) {
    const rawName = attribute.name
    const lowerName = rawName.toLowerCase()
    if (lowerName.startsWith('on')) {
      convertedHandlers.push(lowerName)
      props[toReactEventName(lowerName)] = (event: unknown) => runInlineHandler(attribute.value, event)
      continue
    }
    if (lowerName === 'selected' && element instanceof HTMLOptionElement) continue
    const reactName = lowerName.startsWith('data-') || lowerName.startsWith('aria-')
      ? lowerName
      : attributeNameMap[lowerName] ?? rawName
    if (reactName === 'value' && element instanceof HTMLInputElement) {
      props.defaultValue = attribute.value
      continue
    }
    if (reactName === 'checked' && element instanceof HTMLInputElement) {
      props.defaultChecked = true
      continue
    }
    props[reactName] = attributeValueToReactValue(lowerName, attribute.value)
  }

  if (element instanceof HTMLSelectElement) {
    const selectedOption = Array.from(element.options).find((option) => option.hasAttribute('selected'))
    if (selectedOption) props.defaultValue = selectedOption.value || selectedOption.textContent || ''
  }

  if (element instanceof HTMLTextAreaElement && element.textContent) {
    props.defaultValue = element.textContent
  }

  if (convertedHandlers.length) {
    props['data-vella-react-handlers'] = convertedHandlers.sort().join(',')
  }

  return props
}

function domNodeToReact(node: Node, key: string, replacements: HtmlReactReplacement[] = []): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent
  if (node.nodeType === Node.COMMENT_NODE) return null
  if (!(node instanceof HTMLElement) && !(node instanceof SVGElement)) return null
  const replacement = replacements.find((item) => node.matches(item.selector))
  if (replacement) return createElement(Fragment, { key }, replacement.render(key, node))

  const props = {
    key,
    ...elementAttributesToProps(node),
  }
  if (node instanceof HTMLTextAreaElement) return createElement('textarea', props)
  const tableChildTags = new Set(['table', 'thead', 'tbody', 'tfoot', 'tr', 'colgroup'])
  const shouldDropWhitespaceText = tableChildTags.has(node.tagName.toLowerCase())
  const childNodes = Array.from(node.childNodes)
    .filter((child) => !(shouldDropWhitespaceText && child.nodeType === Node.TEXT_NODE && !child.textContent?.trim()))
  const children = childNodes.map((child, index) => domNodeToReact(child, `${key}-${index}`, replacements))
  return children.length
    ? createElement(node.tagName.toLowerCase(), props, ...children)
    : createElement(node.tagName.toLowerCase(), props)
}

export function htmlToReactFragment(html: string, label: string, replacements: HtmlReactReplacement[] = []) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(`<template>${html}</template>`, 'text/html')
  const template = doc.querySelector('template')
  const nodes = Array.from(template?.content.childNodes ?? [])
  return (
    <Fragment key={label}>
      {nodes.map((node, index) => domNodeToReact(node, `${label}-${index}`, replacements))}
    </Fragment>
  )
}
