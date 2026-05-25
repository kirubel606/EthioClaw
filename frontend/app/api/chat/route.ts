import type { NextRequest } from 'next/server'
import { BACKEND_URL } from '@/lib/server-env'

export const runtime = 'nodejs'

export async function POST(req: NextRequest) {
  try {
    const { messages, session_id } = await req.json()
    // Concatenate all text parts if using the new format, otherwise fallback
    let userMessage: string
    if (Array.isArray(messages)) {
      // Assume messages are in the shape [{ role, content }]
      // Find the last user message
      const lastUser = messages.filter((m: any) => m.role === 'user').pop()
      userMessage = lastUser?.content || ''
    } else if (messages?.message) {
      userMessage = messages.message
    } else {
      userMessage = ''
    }

    const backendResponse = await fetch(`${BACKEND_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage, session_id: session_id || 'default' })
    })

    if (!backendResponse.ok) {
      console.error('[v0] Backend chat error:', backendResponse.statusText)
      return new Response('Backend error', { status: 502 })
    }
    const data = await backendResponse.json()
    // Return the assistant response as plain text (you could stream if needed)
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })
  } catch (error) {
    console.error('[v0] Chat API error:', error)
    return new Response('Internal server error', { status: 500 })
  }
}
