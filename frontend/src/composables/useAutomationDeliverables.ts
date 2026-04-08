import { ref } from 'vue';
import {
  fetchAutomationOutputs,
  buildOutputDownloadUrl,
  type AutomationOutput,
} from '@/api/automationService';
import apiClient from '@/api/apiClient';
import tokenService from '@/api/tokenService';
import api from '@/services/api';

export interface DeliverableFiles {
  json?: AutomationOutput;
  markdown?: AutomationOutput;
  other?: AutomationOutput[];
}

export interface DeliverableItem {
  id: string;
  agent: string;
  createdAt: number;
  sizeBytes: number;
  files: DeliverableFiles;
  /** Entregable persistido vía /api/v1/workspace (document_approvals) */
  isWorkspace?: boolean;
  workspacePayload?: Record<string, unknown>;
  displayTitle?: string;
}

const EXTENSION_REGEX = /\.(json|md|markdown)$/i;

function groupOutputs(outputs: AutomationOutput[]): DeliverableItem[] {
  const map: Record<string, DeliverableItem> = {};

  outputs.forEach((output) => {
    const base = output.path.replace(EXTENSION_REGEX, '');
    if (!map[base]) {
      map[base] = {
        id: base,
        agent: output.agent,
        createdAt: output.created_at,
        sizeBytes: output.size_bytes,
        files: {},
      };
    }

    const entry = map[base];
    entry.createdAt = Math.max(entry.createdAt, output.created_at);
    entry.sizeBytes += output.size_bytes;

    if (output.path.toLowerCase().endsWith('.json')) {
      entry.files.json = output;
    } else if (output.path.toLowerCase().endsWith('.md') || output.path.toLowerCase().endsWith('.markdown')) {
      entry.files.markdown = output;
    } else {
      if (!entry.files.other) entry.files.other = [];
      entry.files.other!.push(output);
    }
  });

  return Object.values(map).sort((a, b) => b.createdAt - a.createdAt);
}

export function useAutomationDeliverables(agent: string) {
  const items = ref<DeliverableItem[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const load = async () => {
    isLoading.value = true;
    error.value = null;
    try {
      const outputs = await fetchAutomationOutputs(agent);
      let merged = groupOutputs(outputs);
      if (agent === 'PERSEO') {
        try {
          const ws = await api.get('/api/v1/workspace/list?agent_name=PERSEO&limit=100');
          if (ws?.success && Array.isArray(ws.items)) {
            const wsItems: DeliverableItem[] = ws.items.map((doc: Record<string, unknown>) => {
              const payload = (doc.document_payload || {}) as Record<string, unknown>;
              const created = doc.created_at ? new Date(String(doc.created_at)).getTime() / 1000 : 0;
              return {
                id: `ws:${doc.id}`,
                agent: 'PERSEO',
                createdAt: Number.isFinite(created) ? created : 0,
                sizeBytes: 0,
                files: {},
                isWorkspace: true,
                workspacePayload: payload,
                displayTitle:
                  (typeof payload.title === 'string' && payload.title) ||
                  (typeof doc.document_type === 'string' && doc.document_type) ||
                  `Entregable #${doc.id}`,
              };
            });
            merged = [...wsItems, ...merged].sort((a, b) => b.createdAt - a.createdAt);
          }
        } catch (e) {
          console.warn('Workspace list PERSEO no disponible', e);
        }
      }
      items.value = merged;
    } catch (err) {
      console.error(`Error fetching outputs for agent ${agent}`, err);
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      isLoading.value = false;
    }
  };

  const buildDownloadLinkFor = (file?: AutomationOutput) => {
    if (!file) return '';
    // Incluir token en la URL para descargas directas
    const token = tokenService.getToken();
    const baseUrl = buildOutputDownloadUrl(file.path);
    return token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
  };

  const fetchDeliverableData = async (deliverable: DeliverableItem) => {
    if (deliverable.isWorkspace && deliverable.workspacePayload) {
      return {
        workspace_deliverable: true,
        payload: deliverable.workspacePayload,
      };
    }
    if (!deliverable.files.json) return null;
    const [agent, filename] = deliverable.files.json.path.split('/');
    // Usar axios para incluir el token automáticamente
    const response = await apiClient.get(`/automation/outputs/${agent}/${filename}`);
    return response.data;
  };

  return {
    items,
    isLoading,
    error,
    load,
    buildDownloadLinkFor,
    fetchDeliverableData,
  };
}

