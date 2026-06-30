import { describe, expect, it } from 'vitest'
import {
  FORBIDDEN_AI_FALLBACK_PHRASES,
  isForbiddenAiFallback,
  resolveMediaUploadState,
  sanitizeAgentChatForMediaFlow,
} from '@/utils/mediaUploadPolicy'

describe('mediaUploadPolicy', () => {
  it('resolves strict upload states', () => {
    expect(resolveMediaUploadState({ isUploading: false, hasError: false, hasUploaded: false, hasFile: false })).toBe(
      'idle',
    )
    expect(resolveMediaUploadState({ isUploading: false, hasError: false, hasUploaded: false, hasFile: true })).toBe(
      'file_selected',
    )
    expect(resolveMediaUploadState({ isUploading: true, hasError: false, hasUploaded: false, hasFile: true })).toBe(
      'uploading',
    )
  })

  it('detects forbidden AI fallback phrases', () => {
    for (const phrase of FORBIDDEN_AI_FALLBACK_PHRASES) {
      expect(isForbiddenAiFallback(`Prefix ${phrase} suffix`)).toBe(true)
    }
  })

  it('sanitizes media-only flow without LLM apology', () => {
    const out = sanitizeAgentChatForMediaFlow('Lo siento por la confusión, no tengo la capacidad de crear vídeos', {
      hadMediaOnly: true,
    })
    expect(out).toContain('Archivo listo')
    expect(out.toLowerCase()).not.toContain('confusión')
  })
})
