/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public base domain, e.g. "edunova.com". Slugs are read from hostnames like "{slug}.edunova.com". */
  readonly VITE_PLATFORM_BASE_DOMAIN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
