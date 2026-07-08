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

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_RUNTIME_API_BASE?: string;
  readonly VITE_WS_URL?: string;
  readonly REACT_APP_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare class BarcodeDetector {
  constructor(options?: { formats?: string[] })
  detect(image: ImageBitmapSource): Promise<Array<{ rawValue: string }>>
}

declare module 'jsqr' {
  interface QRCode {
    binaryData: number[]
    data: string
    chunks: unknown[]
    version: number
    location: {
      topRightCorner: { x: number; y: number }
      topLeftCorner: { x: number; y: number }
      bottomRightCorner: { x: number; y: number }
      bottomLeftCorner: { x: number; y: number }
      topRightFinderPattern: { x: number; y: number }
      topLeftFinderPattern: { x: number; y: number }
      bottomLeftFinderPattern: { x: number; y: number }
    }
  }

  export default function jsQR(
    data: Uint8ClampedArray,
    width: number,
    height: number,
    options?: { inversionAttempts?: 'dontInvert' | 'onlyInvert' | 'attemptBoth' | 'invertFirst' },
  ): QRCode | null
}

declare module '@capacitor/core' {
  export const Capacitor: {
    isNativePlatform: () => boolean
    getPlatform: () => string
  }
}

declare module '@capacitor/camera' {
  export const Camera: {
    getPhoto: (opts: Record<string, unknown>) => Promise<{ base64String?: string }>
  }
  export const CameraResultType: { Base64: string }
  export const CameraSource: { Camera: string }
}

declare module '@capgo/capacitor-nfc' {
  export const CapacitorNfc: {
    addListener: (
      event: string,
      cb: (ev: { tag?: { message?: string; data?: string } }) => void,
    ) => Promise<{ remove: () => void }>
    startScanning: () => Promise<void>
    stopScanning: () => Promise<void>
  }
}
