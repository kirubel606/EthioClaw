'use client'

import { useState } from 'react'
import { Plus, Trash2, Edit2, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface MemoryInspectorProps {
  memories: any[]
  onAddMemory?: (fact: string) => void
  onDeleteMemory?: (id: string) => void
  onEditMemory?: (id: string, value: string) => void
}

export default function MemoryInspector({ memories, onAddMemory, onDeleteMemory, onEditMemory }: MemoryInspectorProps) {
  const [newMemory, setNewMemory] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const handleAdd = () => {
    if (newMemory.trim() && onAddMemory) {
      onAddMemory(newMemory)
      setNewMemory('')
    }
  }

  const startEdit = (m: any) => {
    setEditingId(m.id)
    setEditValue(m.value)
  }

  const saveEdit = (id: string) => {
    if (onEditMemory) onEditMemory(id, editValue)
    setEditingId(null)
  }

  return (
    <div className="h-full flex flex-col bg-card border-l border-border">
      <div className="border-b border-border p-4 flex items-center justify-between">
        <h2 className="font-bold text-foreground">Memory Bank</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {onAddMemory && (
          <div className="flex gap-2">
            <input
              value={newMemory}
              onChange={(e) => setNewMemory(e.target.value)}
              placeholder="New fact (key: value)"
              className="flex-1 bg-background border border-border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <Button onClick={handleAdd} size="sm"><Plus size={16}/></Button>
          </div>
        )}

        {memories.map((m) => (
          <div key={m.id} className="bg-background border border-border rounded-lg p-3 group">
            {editingId === m.id ? (
              <div className="flex gap-2">
                <input
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="flex-1 bg-card border border-border rounded px-2 py-1 text-xs"
                />
                <Button onClick={() => saveEdit(m.id)} size="sm" variant="ghost"><Check size={14}/></Button>
                <Button onClick={() => setEditingId(null)} size="sm" variant="ghost"><X size={14}/></Button>
              </div>
            ) : (
              <div className="flex justify-between items-start gap-2">
                <div>
                  <p className="text-foreground font-bold text-sm">{m.key}</p>
                  <p className="text-muted-foreground text-xs">{m.value}</p>
                </div>
                {onDeleteMemory && (
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button onClick={() => startEdit(m)} size="sm" variant="ghost" className="h-6 w-6 p-0"><Edit2 size={12}/></Button>
                    <Button onClick={() => onDeleteMemory(m.id)} size="sm" variant="ghost" className="h-6 w-6 p-0 text-destructive"><Trash2 size={12}/></Button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="border-t border-border p-4 text-center">
        <p className="text-muted-foreground text-xs"><span className="font-bold text-foreground">{memories.length}</span> Facts Stored</p>
      </div>
    </div>
  )
}
