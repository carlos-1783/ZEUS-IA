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

/**
 * Historial persistido GET /api/v1/chat/messages
 */
export function getChatMessagesUrl(agentDisplayName: string, threadId = 'main'): string {
  const base = API_BASE_URL.replace(/\/+$/, '');
  const params = new URLSearchParams({
    agent_name: agentDisplayName,
    thread_id: threadId,
  });
  return `${base}/chat/messages?${params.toString()}`;
}

/**
 * J10: evidencia enlazada en la respuesta del chat. Los entregables NO se incrustan en el mensaje:
 * `url` es el endpoint del recurso (exige sesión y filtra por empresa en el servidor).
 */
export type ChatEvidenceKind =
  | 'document'
  | 'approval'
  | 'invoice'
  | 'movement'
  | 'route'
  | 'customer'
  | 'audit'
  | 'activity';

export interface ChatEvidence {
  kind: ChatEvidenceKind;
  id: number | string;
  agent: string;
  title: string;
  url: string;
  status: string;
}

export interface ChatResponseData {
  agent?: string;
  message?: string;
  success?: boolean;
  error?: string | null;
  workspace_document_id?: number | null;
  needs_confirmation?: boolean | null;
  approval_id?: number | null;
  request_id?: string | null;
  warnings?: string[] | null;
  evidence?: ChatEvidence[] | null;
  next_step?: string | null;
  [key: string]: unknown;
}

/** Campos J10 que la UI conserva junto al mensaje del agente. */
export interface ChatExtras {
  evidence: ChatEvidence[];
  nextStep: string | null;
  needsConfirmation: boolean;
}

export function extractChatExtras(data: ChatResponseData | null | undefined): ChatExtras {
  const evidence = Array.isArray(data?.evidence) ? data!.evidence!.filter((e) => e && e.url) : [];
  return {
    evidence,
    nextStep: data?.next_step ? String(data.next_step) : null,
    needsConfirmation: Boolean(data?.needs_confirmation && data?.approval_id),
  };
}

/** `url` de evidencia (ruta absoluta del API) -> URL completa sobre el origen configurado. */
export function resolveEvidenceUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  const origin = API_BASE_URL.replace(/\/+$/, '').replace(/\/api(\/v\d+)?$/i, '');
  return `${origin}${url.startsWith('/') ? '' : '/'}${url}`;
}

/** Abre el recurso enlazado con la sesión del usuario (un enlace directo no lleva el token). */
export async function openEvidence(item: ChatEvidence, token: string | null): Promise<void> {
  const res = await fetch(resolveEvidenceUrl(item.url), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(res.status === 404 ? 'El recurso ya no está disponible.' : `Error ${res.status}`);
  }
  const body = await res.json();
  const blob = new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' });
  const href = URL.createObjectURL(blob);
  window.open(href, '_blank', 'noopener');
  setTimeout(() => URL.revokeObjectURL(href), 60000);
}
