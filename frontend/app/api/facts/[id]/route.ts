import { promises as fs } from 'fs'
import path from 'path'
import type { NextRequest } from 'next/server'

const factsFile = path.join(process.cwd(), 'data', 'facts.json')

// Ensure data directory exists
async function ensureDataDir() {
  try {
    await fs.mkdir(path.dirname(factsFile), { recursive: true })
  } catch {
    // Directory already exists
  }
}

// Read facts from file
async function readFacts() {
  try {
    await ensureDataDir()
    const data = await fs.readFile(factsFile, 'utf-8')
    return JSON.parse(data)
  } catch {
    return []
  }
}

// Write facts to file
async function writeFacts(facts: any[]) {
  await ensureDataDir()
  await fs.writeFile(factsFile, JSON.stringify(facts, null, 2))
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    const facts = await readFacts()
    const filtered = facts.filter((f: any) => f.id !== id)

    if (filtered.length === facts.length) {
      return Response.json({ error: 'Fact not found' }, { status: 404 })
    }

    await writeFacts(filtered)
    return Response.json({ success: true })
  } catch (error) {
    console.error('[v0] Failed to delete fact:', error)
    return Response.json({ error: 'Failed to delete fact' }, { status: 500 })
  }
}
