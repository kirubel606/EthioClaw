import { promises as fs } from 'fs'
import path from 'path'

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

export async function GET() {
  try {
    const facts = await readFacts()
    return Response.json(facts)
  } catch (error) {
    console.error('[v0] Failed to read facts:', error)
    return Response.json([], { status: 500 })
  }
}

export async function POST(req: Request) {
  try {
    const { fact } = await req.json()

    if (!fact || typeof fact !== 'string') {
      return Response.json({ error: 'Invalid fact' }, { status: 400 })
    }

    const facts = await readFacts()
    const newFact = {
      id: `fact-${Date.now()}`,
      fact: fact.trim(),
      timestamp: new Date().toISOString(),
    }

    facts.push(newFact)
    await writeFacts(facts)

    return Response.json(newFact, { status: 201 })
  } catch (error) {
    console.error('[v0] Failed to add fact:', error)
    return Response.json({ error: 'Failed to add fact' }, { status: 500 })
  }
}
