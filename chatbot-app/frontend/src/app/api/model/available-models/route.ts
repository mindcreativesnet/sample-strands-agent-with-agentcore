/**
 * Available Models endpoint - returns list of supported AI models
 */
import { NextResponse } from 'next/server'

export const runtime = 'nodejs'

// Available Bedrock models
const AVAILABLE_MODELS = [
  {
    id: 'openai.gpt-oss-20b-1:0',
    name: 'GPT-OSS 20B',
    provider: 'OpenAI',
    description: 'Open-source 20 billion parameter model'
  },

]

export async function GET() {
  try {
    return NextResponse.json({
      models: AVAILABLE_MODELS
    })
  } catch (error) {
    console.error('[API] Error loading available models:', error)

    return NextResponse.json({
      models: AVAILABLE_MODELS
    })
  }
}
