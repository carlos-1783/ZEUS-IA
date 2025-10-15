/// <reference types="vite/client" />

declare module '*.vue' {
  import { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

declare module '@/stores/auth' {
  import { StoreDefinition } from 'pinia';
  export const useAuthStore: StoreDefinition;
}

declare module '@/utils/audioService' {
  export function playActivationSound(): void;
  export function playErrorSound(): void;
  export function playSuccessSound(): void;
  export function playNotificationSound(): void;
  export function toggleAudio(enabled: boolean): void;
  export function isAudioEnabled(): boolean;
}

declare module '@/api' {
  export function executeCommand(command: string, params?: Record<string, any>): Promise<any>;
  export function getSystemStatus(): Promise<any>;
  export const auth: {
    login: (credentials: { username: string; password: string; grant_type?: string }) => Promise<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
      token_type?: string;
    }>;
    logout: () => Promise<void>;
    refreshToken: (refreshToken: string) => Promise<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
      token_type?: string;
    }>;
  };
  export const system: {
    getStatus: () => Promise<any>;
    activateCompany: (companyId: string) => Promise<any>;
    deactivateCompany: (companyId: string) => Promise<any>;
  };
  export const commands: {
    execute: (command: string, params?: Record<string, any>) => Promise<any>;
  };
}

declare module '@/utils/tokenService' {
  export function getToken(): string | null;
  export function setToken(token: string): void;
  export function removeToken(): void;
  export function getRefreshToken(): string | null;
  export function setRefreshToken(token: string): void;
  export function removeRefreshToken(): void;
  export function clearAuthTokens(): void;
  export function isTokenExpired(token: string | null): boolean;
  export function getTokenExpiration(token: string | null): number | null;
  export function onTokenRefreshed(callback: (token: string) => void): void;
  export function clearRefreshSubscribers(): void;
  export function notifyRefreshSubscribers(token: string): void;
  export function getIsRefreshing(): boolean;
  export function setIsRefreshing(value: boolean): void;
  export function scheduleTokenRefresh(expirationTime: number): void;
}

// Add missing Web Speech API types
declare class SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: (event: any) => void;
  onerror: (event: any) => void;
  onend: () => void;
  start(): void;
  stop(): void;
  abort(): void;
}

declare var webkitSpeechRecognition: {
  prototype: SpeechRecognition;
  new (): SpeechRecognition;
};

declare interface Window {
  webkitSpeechRecognition: typeof webkitSpeechRecognition;
  SpeechRecognition: typeof webkitSpeechRecognition;
}

// Add missing Vite env variables
interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  // Add other environment variables here
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
