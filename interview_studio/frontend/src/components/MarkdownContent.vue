<script>
import { h } from 'vue'

const INLINE_TOKEN_SOURCE = '\\[([^\\]]+)\\]\\(([^\\s)]+)\\)|`([^`]+)`|\\*\\*([^*]+)\\*\\*|__([^_]+)__|\\*([^*]+)\\*|_([^_]+)_'

function safeHref(value) {
  const href = value.trim()
  return /^(https?:\/\/|mailto:)/i.test(href) ? href : null
}

function inlineNodes(value) {
  const text = String(value ?? '')
  const nodes = []
  let position = 0
  let match

  const token = new RegExp(INLINE_TOKEN_SOURCE, 'g')
  while ((match = token.exec(text))) {
    if (match.index > position) nodes.push(text.slice(position, match.index))

    if (match[1] !== undefined) {
      const href = safeHref(match[2])
      nodes.push(href
        ? h('a', { href, target: '_blank', rel: 'noopener noreferrer' }, inlineNodes(match[1]))
        : match[0])
    } else if (match[3] !== undefined) {
      nodes.push(h('code', match[3]))
    } else if (match[4] !== undefined || match[5] !== undefined) {
      nodes.push(h('strong', inlineNodes(match[4] ?? match[5])))
    } else {
      nodes.push(h('em', inlineNodes(match[6] ?? match[7])))
    }
    position = token.lastIndex
  }

  if (position < text.length) nodes.push(text.slice(position))
  return nodes.length ? nodes : ['']
}

function paragraph(lines, key) {
  const nodes = []
  lines.forEach((line, index) => {
    if (index) nodes.push(h('br'))
    nodes.push(...inlineNodes(line))
  })
  return h('p', { key }, nodes)
}

function renderBlocks(value) {
  const lines = String(value ?? '').replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let index = 0
  let key = 0

  while (index < lines.length) {
    if (!lines[index].trim()) {
      index += 1
      continue
    }

    const fence = lines[index].match(/^```[^`]*$/)
    if (fence) {
      const codeLines = []
      index += 1
      while (index < lines.length && !/^```\s*$/.test(lines[index])) {
        codeLines.push(lines[index])
        index += 1
      }
      if (index < lines.length) index += 1
      blocks.push(h('pre', { key: key++ }, [h('code', codeLines.join('\n'))]))
      continue
    }

    const heading = lines[index].match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      blocks.push(h(`h${heading[1].length}`, { key: key++ }, inlineNodes(heading[2])))
      index += 1
      continue
    }

    const unordered = lines[index].match(/^[-*+]\s+(.+)$/)
    const ordered = lines[index].match(/^\d+[.)]\s+(.+)$/)
    if (unordered || ordered) {
      const listPattern = unordered ? /^[-*+]\s+(.+)$/ : /^\d+[.)]\s+(.+)$/
      const items = []
      while (index < lines.length) {
        const item = lines[index].match(listPattern)
        if (!item) break
        items.push(h('li', { key: items.length }, inlineNodes(item[1])))
        index += 1
      }
      blocks.push(h(unordered ? 'ul' : 'ol', { key: key++ }, items))
      continue
    }

    const paragraphLines = []
    while (index < lines.length && lines[index].trim()) {
      if (paragraphLines.length && (/^```/.test(lines[index]) || /^(#{1,6})\s+/.test(lines[index]) || /^[-*+]\s+/.test(lines[index]) || /^\d+[.)]\s+/.test(lines[index]))) break
      paragraphLines.push(lines[index])
      index += 1
    }
    blocks.push(paragraph(paragraphLines, key++))
  }

  return blocks.length ? blocks : [h('p', { class: 'markdown-empty' }, '내용이 없습니다.')]
}

export default {
  name: 'MarkdownContent',
  props: {
    content: { type: String, default: '' },
    streaming: { type: Boolean, default: false },
  },
  setup(props) {
    return () => h('div', { class: 'markdown-content' }, [
      ...renderBlocks(props.content),
      props.streaming ? h('i', { class: 'stream-caret', 'aria-hidden': 'true' }) : null,
    ])
  },
}
</script>
