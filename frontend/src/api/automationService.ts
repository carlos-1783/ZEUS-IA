import apiClient from './apiClient';
import config from '@/config';

export interface AutomationOutput {
  agent: string;
  filename: string;
  path: string;
  size_bytes: number;
  created_at: number;
}

export async function fetchAutomationOutputs(agent?: string): Promise<AutomationOutput[]> {
  const params = agent ? { agent } : undefined;
  const response = await apiClient.get<{ outputs?: AutomationOutput[] }>('/automation/outputs', { params });
  return response.data.outputs ?? [];
}

export function buildOutputDownloadUrl(path: string): string {
  const [agent, filename] = path.split('/');
  const baseUrl = config.api.baseUrl.replace(/\/$/, '');
  return `${baseUrl}/automation/outputs/${agent}/${filename}`;
}

