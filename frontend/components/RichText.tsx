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
    <div className="my-4 rounded-lg overflow-hidden border border-border bg-background font-mono text-xs sm:text-sm shadow-inner">
      <div className="bg-muted/50 px-4 py-2 flex items-center justify-between border-b border-border text-primary font-bold">
        <span className="uppercase text-[10px] tracking-wider">{lang || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-1 rounded bg-muted hover:bg-muted/80 border border-border text-foreground transition-all duration-200"
          title="Copy to clipboard"
        >
          {copied ? (
            <>
              <Check className="size-3.5 text-green-500" />
              <span className="text-green-500">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="size-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto scrollbar-hidden text-foreground leading-relaxed whitespace-pre">
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
            <span className="relative block rounded-lg overflow-hidden border-2 border-border max-w-md aspect-video shadow-md">
              <Image
                src={url}
                alt={alt || 'Embedded image'}
                fill
                className="object-cover"
                unoptimized
              />
            </span>
            {alt && <span className="text-xs text-muted-foreground mt-1 block text-center italic">{alt}</span>}
          </span>
        )
      }

      // Link: [text](url)
      if (part.startsWith('[') && part.includes('](')) {
        const label = part.substring(1, part.indexOf(']'))
        const url = part.substring(part.indexOf('](') + 2, part.length - 1)
        const isArtifactLink =
          /generated file|download/i.test(label) || /\.(pptx|pdf|docx)$/i.test(url)
        return (
          <a
            key={index}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className={
              isArtifactLink
                ? 'inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground font-bold border border-border shadow-lg hover:opacity-90 transition-all duration-200 no-underline'
                : 'inline-flex items-center gap-0.5 text-primary hover:opacity-80 underline font-semibold transition-colors'
            }
          >
            {label}
            <ExternalLink className="size-3" />
          </a>
        )
      }

      // Bold: **text**
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={index} className="font-extrabold text-primary">
            {part.substring(2, part.length - 2)}
          </strong>
        )
      }

      // Inline code: `code`
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={index} className="px-1.5 py-0.5 rounded bg-muted border border-border text-primary font-mono text-xs sm:text-sm">
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
        <div className="my-4 rounded-lg overflow-hidden border-2 border-border aspect-video max-w-xl shadow-lg">
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
