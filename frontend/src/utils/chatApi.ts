import { API_BASE_URL } from '@/config';

/**
 * Chat con cualquier agente (ZEUS CORE, PERSEO, RAFAEL, THALOS, JUSTICIA, AFRODITA).
 * URL absoluta vía API_BASE_URL: en despliegues split (frontend ≠ API) las rutas relativas fallan.
 *
 * Timeout HTTP (LLM + tareas pesadas en background). Override: VITE_AGENT_CHAT_TIMEOUT_MS.
 */
// Debe ser >= tiempo máximo LLM + colas (Railway/proxy). Default 5 min.
export const AGENT_CHAT_TIMEOUT_MS = Number(
  import.meta.env.VITE_AGENT_CHAT_TIMEOUT_MS || 300000,
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
