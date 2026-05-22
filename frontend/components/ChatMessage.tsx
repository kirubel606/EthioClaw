'use client'

import Image from 'next/image'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatMessage({ role, content }: ChatMessageProps) {
  const isAI = role === 'assistant'

  return (
    <div className={`flex gap-4 mb-6 animate-in fade-in slide-in-from-bottom-3 duration-500 ${isAI ? '' : 'justify-end'}`}>
      {isAI && (
        <div className="flex-shrink-0">
          <div className="rick-avatar relative">
            <Image
              src="/rick-avatar.jpg"
              alt="Rick the AI"
              width={48}
              height={48}
              className="w-full h-full object-cover"
            />
          </div>
        </div>
      )}

      <div className={`flex flex-col ${isAI ? 'items-start' : 'items-end'}`}>
        {isAI && <p className="text-cyan-300 text-xs mb-2 font-semibold">RICK (AI Agent)</p>}

        <div
          className={`message-bubble ${isAI ? 'message-bubble-ai' : 'message-bubble-user'}`}
        >
          <p className="text-sm lg:text-base leading-relaxed whitespace-pre-wrap break-words">
            {content}
          </p>
        </div>

        {isAI && (
          <p className="text-xs text-green-400 mt-1 opacity-70">
            [burp] Portal engaged...
          </p>
        )}
      </div>

      {!isAI && (
        <div className="flex-shrink-0">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center border-2 border-cyan-400 text-white font-bold text-lg">
            M
          </div>
        </div>
      )}
    </div>
  )
}
