'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'

interface Memory {
  id: string
  fact: string
  timestamp: string
}

interface MemoryInspectorProps {
  memories: Memory[]
  onAddMemory?: (fact: string) => void
  onDeleteMemory?: (id: string) => void
}

export default function MemoryInspector({
  memories,
  onAddMemory,
  onDeleteMemory,
}: MemoryInspectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [newFact, setNewFact] = useState('')

  const handleAddMemory = () => {
    if (newFact.trim() && onAddMemory) {
      onAddMemory(newFact)
      setNewFact('')
    }
  }

  return (
    <div className="h-full flex flex-col bg-gradient-to-b from-blue-950 to-purple-950 border-l-2 border-cyan-400">
      {/* Header */}
      <div className="border-b-2 border-cyan-400 p-4 flex items-center justify-between">
        <h2 className="neon-text text-lg">Memory Bank</h2>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="text-cyan-400 hover:text-green-400 transition-colors text-xl"
        >
          {isOpen ? '▼' : '▶'}
        </button>
      </div>

      {/* Content */}
      <div className={`flex-1 overflow-y-auto scrollbar-hidden transition-all duration-300 ${isOpen ? 'block' : 'hidden'}`}>
        {/* Add New Memory */}
        {onAddMemory && (
          <div className="p-4 border-b border-cyan-400/30">
            <div className="flex gap-2">
              <input
                type="text"
                value={newFact}
                onChange={(e) => setNewFact(e.target.value)}
                placeholder="Add a fact..."
                className="flex-1 bg-gray-900 border border-cyan-400/50 rounded px-2 py-1 text-green-400 text-sm placeholder-gray-600 focus:outline-none focus:border-cyan-400"
              />
              <Button
                onClick={handleAddMemory}
                disabled={!newFact.trim()}
                className="bg-green-600 hover:bg-green-500 text-white text-sm px-3 py-1 rounded border border-green-400 disabled:opacity-50"
              >
                +
              </Button>
            </div>
          </div>
        )}

        {/* Memory List */}
        <div className="p-4 space-y-3">
          {memories.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-8">
              No memories yet. Start talking to Rick!
            </p>
          ) : (
            memories.map((memory) => (
              <div
                key={memory.id}
                className="bg-gray-900 border border-cyan-400/30 rounded-lg p-3 hover:border-cyan-400 transition-colors group"
              >
                <div className="flex justify-between items-start gap-2">
                  <p className="text-green-400 text-xs leading-relaxed flex-1">
                    {memory.fact}
                  </p>
                  {onDeleteMemory && (
                    <button
                      onClick={() => onDeleteMemory(memory.id)}
                      className="text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-opacity text-sm font-bold"
                    >
                      ✕
                    </button>
                  )}
                </div>
                <p className="text-gray-500 text-xs mt-2">
                  {new Date(memory.timestamp).toLocaleString()}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer Stats */}
      <div className="border-t-2 border-cyan-400 p-4 text-center">
        <p className="text-cyan-300 text-sm">
          <span className="text-green-400 font-bold">{memories.length}</span> Facts Stored
        </p>
      </div>
    </div>
  )
}
