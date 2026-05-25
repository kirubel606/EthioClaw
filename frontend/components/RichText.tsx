'use client'

import { useState } from 'react'
import { Copy, Check, ExternalLink } from 'lucide-react'
import Image from 'next/image'

interface RichTextProps {
  content: string
}

interface Block {
  type: 'text' | 'code'
  content: string
  lang?: string
}

// Parses text into code blocks and plain text blocks
function parseBlocks(text: string): Block[] {
  if (!text) return []
  const parts = text.split(/(```[\s\S]*?```)/g)
  return parts.map((part) => {
    if (part.startsWith('```') && part.endsWith('```')) {
      const firstLineEnd = part.indexOf('\n')
      const lang = part.substring(3, firstLineEnd === -1 ? part.length - 3 : firstLineEnd).trim()
      const content = firstLineEnd === -1 
        ? '' 
        : part.substring(firstLineEnd + 1, part.length - 3).trim()
      return { type: 'code', content, lang }
    }
    return { type: 'text', content: part }
  })
}

// Custom Code Block component with Copy button
function CodeBlock({ code, lang }: { code: string; lang?: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy text: ', err)
    }
  }

  return (
    <div className="my-4 rounded-lg overflow-hidden border border-cyan-400 bg-gray-950 font-mono text-xs sm:text-sm">
      <div className="bg-gray-900 px-4 py-2 flex items-center justify-between border-b border-cyan-400/30 text-cyan-300">
        <span className="uppercase text-[10px] tracking-wider font-bold">{lang || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-1 rounded bg-cyan-950 hover:bg-cyan-900 border border-cyan-400/50 hover:border-cyan-400 text-cyan-300 transition-all duration-200"
          title="Copy to clipboard"
        >
          {copied ? (
            <>
              <Check className="size-3.5 text-green-400" />
              <span className="text-green-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="size-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto scrollbar-hidden text-green-400 leading-relaxed whitespace-pre">
        <code>{code}</code>
      </pre>
    </div>
  )
}

// Parses inline elements: Bold, Links, Images, Inline Code, YouTube links
function InlineText({ text }: { text: string }) {
  if (!text) return null

  // Extract YouTube ID if any exists
  const ytRegex = /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})/i
  const ytMatch = text.match(ytRegex)
  const ytId = ytMatch ? ytMatch[1] : null

  // Render inline elements using structured splits
  // First, parse bold, inline code, images, and links
  const renderInline = (input: string) => {
    // Split by Markdown elements
    const parts = input.split(/(!\[.*?\]\(.*?\)|\[.*?\]\(.*?\)|\*\*.*?\*\*|`.*?`)/g)

    return parts.map((part, index) => {
      // Image: ![alt](url)
      if (part.startsWith('![') && part.includes('](')) {
        const alt = part.substring(2, part.indexOf(']'))
        const url = part.substring(part.indexOf('](') + 2, part.length - 1)
        return (
          <span key={index} className="block my-3">
            <span className="relative block rounded-lg overflow-hidden border-2 border-cyan-400 max-w-md aspect-video">
              <Image
                src={url}
                alt={alt || 'Embedded image'}
                fill
                className="object-cover"
                unoptimized
              />
            </span>
            {alt && <span className="text-xs text-gray-500 mt-1 block text-center italic">{alt}</span>}
          </span>
        )
      }

      // Link: [text](url)
      if (part.startsWith('[') && part.includes('](')) {
        const label = part.substring(1, part.indexOf(']'))
        const url = part.substring(part.indexOf('](') + 2, part.length - 1)
        return (
          <a
            key={index}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 text-cyan-400 hover:text-cyan-300 underline font-semibold transition-colors"
          >
            {label}
            <ExternalLink className="size-3" />
          </a>
        )
      }

      // Bold: **text**
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={index} className="font-extrabold text-cyan-300">
            {part.substring(2, part.length - 2)}
          </strong>
        )
      }

      // Inline code: `code`
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-gray-900 border border-cyan-400/30 text-green-400 font-mono text-xs sm:text-sm">
            {part.substring(1, part.length - 1)}
          </code>
        )
      }

      return part
    })
  }

  // Split content by newline to render proper paragraph structures
  const paragraphs = text.split('\n')

  return (
    <div className="space-y-2">
      {paragraphs.map((para, idx) => {
        if (!para.trim()) return <div key={idx} className="h-2" />
        return (
          <p key={idx} className="text-sm lg:text-base leading-relaxed whitespace-pre-wrap break-words">
            {renderInline(para)}
          </p>
        )
      })}

      {/* YouTube Embed */}
      {ytId && (
        <div className="my-4 rounded-lg overflow-hidden border-2 border-cyan-400 aspect-video max-w-xl shadow-lg shadow-cyan-500/10">
          <iframe
            width="100%"
            height="100%"
            src={`https://www.youtube.com/embed/${ytId}`}
            title="YouTube video player"
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            className="w-full h-full"
          />
        </div>
      )}
    </div>
  )
}

export default function RichText({ content }: RichTextProps) {
  const blocks = parseBlocks(content)

  return (
    <div className="space-y-1">
      {blocks.map((block, idx) => {
        if (block.type === 'code') {
          return <CodeBlock key={idx} code={block.content} lang={block.lang} />
        }
        return <InlineText key={idx} text={block.content} />
      })}
    </div>
  )
}
