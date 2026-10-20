/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_WS_URL: string;
  /** Picovoice (palabra de activación del orbe). Sin clave, el orbe funciona sin escucha en espera. */
  readonly VITE_PICOVOICE_ACCESS_KEY?: string;
  readonly VITE_PICOVOICE_KEYWORD_PATH?: string;
  readonly VITE_PICOVOICE_KEYWORD_LABEL?: string;
  readonly VITE_PICOVOICE_MODEL_PATH?: string;
  // add more environment variables here as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
