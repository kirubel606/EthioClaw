import { useState, useImperativeHandle, forwardRef, useRef, KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'

export interface ChatInputRef {
  appendQuote: (text: string) => void
  clearFiles: () => void
}

interface ChatInputProps {
  onSubmit: (message: string) => void | Promise<void>
  onFilesSelected?: (files: File[]) => void | Promise<void>
  isLoading?: boolean
  isUploading?: boolean
}

export const ChatInput = forwardRef<ChatInputRef, ChatInputProps>(
  ({ onSubmit, onFilesSelected, isLoading, isUploading }, ref) => {
    const [input, setInput] = useState('')
    const [selectedFiles, setSelectedFiles] = useState<string[]>([])
    const inputRef = useRef<HTMLTextAreaElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    useImperativeHandle(ref, () => ({
      appendQuote(text: string) {
        setInput((prev) => `> "${text}"\n\n${prev}`)
        setTimeout(() => {
          inputRef.current?.focus()
        }, 50)
      },
      clearFiles() {
        setSelectedFiles([])
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      },
    }))

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault()
      if (input.trim() && !isLoading && !isUploading) {
        try {
          await onSubmit(input)
          setInput('')
        } catch (error) {
          console.error('[v0] Failed to submit chat input:', error)
        }
      }
    }

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit(e as unknown as React.FormEvent)
      }
    }

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || [])
      if (!files.length) return

      setSelectedFiles(files.map((file) => file.name))

      try {
        await onFilesSelected?.(files)
      } catch (error) {
        console.error('[v0] Failed to hand files to parent:', error)
      } finally {
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      }
    }

    return (
      <form
        onSubmit={handleSubmit}
        className="border-t-2 border-border bg-card p-6 shadow-lg"
      >
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything... (Shift+Enter for newline)"
              disabled={isLoading || isUploading}
              className="w-full bg-background border-2 border-border rounded-lg px-4 py-3 text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all duration-200 hover:border-primary/50 resize-none min-h-[50px] max-h-[200px]"
              rows={1}
            />
          </div>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.txt,.csv,application/pdf,text/plain,text/csv"
            onChange={handleFileChange}
            className="hidden"
          />

          <Button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || isUploading}
            className="bg-accent hover:bg-accent/90 text-accent-foreground font-bold px-4 py-3 rounded-lg border-2 border-border transition-all duration-200 hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? 'Uploading...' : 'Upload'}
          </Button>

          <Button
            type="submit"
            disabled={isLoading || isUploading || !input.trim()}
            className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold px-6 py-3 rounded-lg border-2 border-border transition-all duration-200 hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Thinking...' : 'Send'}
          </Button>
        </div>
      </form>
    )
  }
)

export default ChatInput
