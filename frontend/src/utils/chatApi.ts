import { API_BASE_URL } from '@/config';

/** Timeout HTTP para chat con agentes (LLM + posible vídeo en background). */
export const AGENT_CHAT_TIMEOUT_MS = Number(
  import.meta.env.VITE_AGENT_CHAT_TIMEOUT_MS || 180000,
);

/**
 * URL absoluta del endpoint POST de chat del agente.
 * No usar rutas relativas: en producción el frontend suele estar en otro origen que el API.
 */
export function getAgentChatUrl(agentDisplayName: string): string {
  const agentNameUrl = agentDisplayName.toLowerCase().replace(/ /g, '-');
  const base = API_BASE_URL.replace(/\/+$/, '');
  return `${base}/chat/${agentNameUrl}/chat`;
}
