import { useState, useImperativeHandle, forwardRef, useRef } from 'react'
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
    const inputRef = useRef<HTMLInputElement>(null)
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
        className="border-t-2 border-cyan-400 bg-gradient-to-r from-blue-950 to-purple-950 p-6 shadow-lg"
      >
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Rick anything... or upload a PDF, TXT, or CSV"
              disabled={isLoading || isUploading}
              className="w-full bg-gray-900 border-2 border-cyan-400 rounded-lg px-4 py-3 text-green-400 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-cyan-300 focus:border-transparent transition-all duration-200 hover:border-green-400"
            />
            <div className="absolute right-3 top-1/2 transform -translate-y-1/2 text-cyan-400 text-xs">
              ▶
            </div>
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
            className="bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-bold px-4 py-3 rounded-lg border-2 border-cyan-300 transition-all duration-200 hover:shadow-lg hover:shadow-cyan-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin">⟳</span>
                Uploading...
              </span>
            ) : (
              'Upload'
            )}
          </Button>

          <Button
            type="submit"
            disabled={isLoading || isUploading || !input.trim()}
            className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold px-6 py-3 rounded-lg border-2 border-cyan-300 transition-all duration-200 hover:shadow-lg hover:shadow-cyan-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin">⟳</span>
                Thinking...
              </span>
            ) : (
              'Send'
            )}
          </Button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-500">
          <p className="mr-3">💬 Press Enter or click Send</p>
          <p className="text-green-400 mr-3">█ Connected</p>
          {selectedFiles.length > 0 && (
            <p className="text-cyan-300">
              Selected: {selectedFiles.join(', ')}
            </p>
          )}
        </div>
      </form>
    )
  }
)

export default ChatInput
