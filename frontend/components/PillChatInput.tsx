import { useState, useRef, ChangeEvent, useImperativeHandle, forwardRef, KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Plus, SendHorizontal, Loader2 } from 'lucide-react'

interface PillChatInputProps {
  onSubmit: (message: string) => void | Promise<void>
  onFilesSelected: (files: File[]) => void | Promise<void>
  isLoading?: boolean
}

export interface ChatInputRef {
  appendQuote: (text: string) => void
  clearInput: () => void
}

export const PillChatInput = forwardRef<ChatInputRef, PillChatInputProps>(
  ({ onSubmit, onFilesSelected, isLoading }, ref) => {
  const [input, setInput] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useImperativeHandle(ref, () => ({
    appendQuote(text: string) {
      setInput((prev) => `${prev}\n> "${text}"\n\n`)
      setTimeout(() => textareaRef.current?.focus(), 50)
    },
    clearInput() {
      setInput('')
      if (textareaRef.current) {
        textareaRef.current.style.height = '44px'
      }
    }
  }))

  const handleSubmit = async () => {
    if (input.trim() && !isLoading) {
      await onSubmit(input)
      setInput('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length > 0) {
      await onFilesSelected(files)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="w-full px-6 py-4">
      <div className="max-w-4xl mx-auto flex items-end gap-2 bg-slate-900/90 backdrop-blur-md p-2 rounded-full border border-slate-700 shadow-2xl focus-within:ring-2 focus-within:ring-cyan-500/50 transition-all">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          multiple
          className="hidden"
          accept=".pdf,.txt,.csv,application/pdf,text/plain,text/csv"
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          className="rounded-full size-10 shrink-0 text-slate-400 hover:text-white"
        >
          <Plus size={20} />
        </Button>
        
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isLoading ? "AI is thinking..." : "Ask anything"}
          disabled={isLoading}
          className="flex-1 bg-transparent border-none outline-none py-3 px-2 text-white placeholder-slate-500 resize-none max-h-[150px] min-h-[44px] leading-6"
          rows={1}
          style={{ height: 'auto', minHeight: '44px' }}
          onInput={(e) => {
            e.currentTarget.style.height = 'auto'
            e.currentTarget.style.height = `${Math.min(e.currentTarget.scrollHeight, 150)}px`
          }}
        />

        <Button
          type="button"
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading}
          className={`rounded-full size-10 shrink-0 transition-all ${
            input.trim() ? 'bg-cyan-600 hover:bg-cyan-500 text-white' : 'bg-slate-800 text-slate-600'
          }`}
        >
          {isLoading ? <Loader2 size={20} className="animate-spin" /> : <SendHorizontal size={20} />}
        </Button>
      </div>
    </div>
  )
})

PillChatInput.displayName = 'PillChatInput'
export default PillChatInput
