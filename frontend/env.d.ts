/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_WS_URL: string;
  /** openWakeWord (palabra de activación del orbe). Sin modelo, el orbe funciona sin escucha en espera. */
  readonly VITE_WAKEWORD_MODEL_PATH?: string;
  readonly VITE_WAKEWORD_LABEL?: string;
  readonly VITE_WAKEWORD_THRESHOLD?: string;
  readonly VITE_WAKEWORD_MELSPECTROGRAM_PATH?: string;
  readonly VITE_WAKEWORD_EMBEDDING_PATH?: string;
  // add more environment variables here as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
