import { ref } from 'vue';
import {
  fetchAutomationOutputs,
  buildOutputDownloadUrl,
  type AutomationOutput,
} from '@/api/automationService';
import apiClient from '@/api/apiClient';
import tokenService from '@/api/tokenService';
import api from '@/services/api';
import { fetchThalosWorkspaceItems } from '@/api/thalos_workspace_api';

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
  fileUrl?: string;
  mimeType?: string;
  fiscalDocType?: string;
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
      let merged = groupOutputs(outputs ?? []);
      const workspaceAgents = new Set(['PERSEO', 'RAFAEL', 'JUSTICIA', 'THALOS', 'AFRODITA']);
      const agentKey = String(agent || '').toUpperCase();
      if (workspaceAgents.has(agentKey)) {
        try {
          const ws = await api.get(`/api/v1/workspace/list?agent_name=${encodeURIComponent(agentKey)}&limit=100`);
          const wsItemsRaw = Array.isArray(ws?.items) ? ws.items : [];
          if (ws?.success !== false) {
            const wsItems: DeliverableItem[] = wsItemsRaw.map((doc: Record<string, unknown>) => {
              const payload = (doc.document_payload || {}) as Record<string, unknown>;
              const content = (payload.content || {}) as Record<string, unknown>;
              const fileSize = Number(
                doc.file_size_bytes ?? content.file_size ?? 0,
              );
              const fileUrl =
                (typeof content.file_url === 'string' && content.file_url) ||
                (typeof doc.file_path === 'string' && doc.file_path
                  ? `/static/${String(doc.file_path).split('/static/').pop()}`
                  : '') ||
                '';
              const hasRealFile = fileSize > 0 && !!fileUrl;
              const hasUsefulContent =
                hasRealFile ||
                (typeof payload.title === 'string' && payload.title.trim().length > 0) ||
                (typeof content.copy === 'string' && content.copy.trim().length > 0) ||
                (typeof content.body === 'string' && content.body.trim().length > 0);
              if (!hasUsefulContent) {
                return null as unknown as DeliverableItem;
              }
              if (agentKey === 'RAFAEL' && !hasRealFile && fileSize <= 0) {
                const isLegacyJsonOnly =
                  !content.only_real_file &&
                  !(content.file_path || content.file_url);
                if (isLegacyJsonOnly) {
                  return null as unknown as DeliverableItem;
                }
              }
              const created = doc.created_at ? new Date(String(doc.created_at)).getTime() / 1000 : 0;
              return {
                id: `ws:${doc.id}`,
                agent: agentKey,
                createdAt: Number.isFinite(created) ? created : 0,
                sizeBytes: fileSize,
                files: {},
                isWorkspace: true,
                workspacePayload: payload,
                fileUrl: fileUrl || undefined,
                mimeType:
                  (typeof doc.mime_type === 'string' && doc.mime_type) ||
                  (typeof content.mime_type === 'string' && content.mime_type) ||
                  undefined,
                fiscalDocType:
                  (typeof doc.fiscal_document_type === 'string' && doc.fiscal_document_type) ||
                  (typeof content.fiscal_document_type === 'string' && content.fiscal_document_type) ||
                  undefined,
                displayTitle:
                  (typeof payload.title === 'string' && payload.title) ||
                  (typeof doc.document_type === 'string' && doc.document_type) ||
                  `Entregable #${doc.id}`,
              };
            }).filter(Boolean);
            merged = [...wsItems, ...merged].sort((a, b) => b.createdAt - a.createdAt);
          }
        } catch (e) {
          console.warn(`Workspace list ${agentKey} no disponible`, e);
        }
      }
      if (agentKey === 'THALOS') {
        try {
          const th = await fetchThalosWorkspaceItems(100);
          const thItemsRaw = Array.isArray(th?.items) ? th.items : [];
          if (th?.success !== false) {
            const thItems: DeliverableItem[] = thItemsRaw.map((item) => {
              const created = item.created_at ? new Date(item.created_at).getTime() / 1000 : 0;
              const sizeBytes = Math.max((item.data_size_kb || 1) * 1024, 1024);
              return {
                id: `thalos:${item.id}`,
                agent: 'THALOS',
                createdAt: Number.isFinite(created) ? created : 0,
                sizeBytes,
                files: {},
                isWorkspace: true,
                displayTitle: item.title || `THALOS ${item.type}`,
                workspacePayload: {
                  title: item.title,
                  content: item.payload,
                  thalos_item_type: item.type,
                  thalos_status: item.status,
                  format: 'thalos_workspace_v1',
                  file_size: sizeBytes,
                },
              };
            });
            merged = [...thItems, ...merged].sort((a, b) => b.createdAt - a.createdAt);
          }
        } catch (e) {
          console.warn('THALOS workspace items no disponibles', e);
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
      const payload = deliverable.workspacePayload;
      const content = (payload.content || {}) as Record<string, unknown>;
      if (deliverable.id.startsWith('thalos:') || payload.thalos_item_type) {
        const scan = (content.real_scan || content.result || content) as Record<string, unknown>;
        const alerts = (scan.pattern_alerts as unknown[]) || [];
        return {
          executed_at: scan.executed_at || content.executed_at,
          pattern_alerts: scan.pattern_alerts,
          failed_login_candidates: scan.failed_login_candidates,
          risk_level: scan.risk_level,
          result: `Riesgo: ${String(scan.risk_level || 'ok')} · ${alerts.length} alertas`,
          checks: content.checks || scan.checks,
          missing: content.missing || scan.missing,
          recommendations: content.recommendations || scan.recommendation,
          configuration: content.configuration,
          actions_performed: content.actions_performed,
          backup_created: content.backup_created ?? scan.backup_created,
          backup_path: content.backup_path ?? scan.backup_path,
          source_exists: content.source_exists ?? scan.source_exists,
          notes: content.notes ?? scan.notes,
        };
      }
      if (content.format === 'thalos_workspace_v1') {
        return content;
      }
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

