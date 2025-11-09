import { ref } from 'vue';
import {
  fetchAutomationOutputs,
  buildOutputDownloadUrl,
  type AutomationOutput,
} from '@/api/automationService';

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
      items.value = groupOutputs(outputs);
    } catch (err) {
      console.error(`Error fetching outputs for agent ${agent}`, err);
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      isLoading.value = false;
    }
  };

  const buildDownloadLinkFor = (file?: AutomationOutput) =>
    file ? buildOutputDownloadUrl(file.path) : '';

  const fetchDeliverableData = async (deliverable: DeliverableItem) => {
    if (!deliverable.files.json) return null;
    const url = buildDownloadLinkFor(deliverable.files.json);
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) {
      throw new Error(`No se pudo cargar el entregable (${response.status})`);
    }
    return response.json();
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

