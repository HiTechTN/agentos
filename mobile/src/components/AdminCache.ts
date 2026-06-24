import AsyncStorage from '@react-native-async-storage/async-storage';

const ADMIN_CACHE_KEY = '@agentos_admin_cache';
const ADMIN_CACHE_TTL = 60_000; // 60s

interface AdminCacheData {
  settings?: Record<string, any>;
  services?: Record<string, any>;
  llmModels?: Record<string, any>;
  users?: Array<Record<string, any>>;
  timestamp: number;
}

let _memoryCache: AdminCacheData | null = null;

export async function getAdminCache(): Promise<AdminCacheData | null> {
  if (_memoryCache && Date.now() - _memoryCache.timestamp < ADMIN_CACHE_TTL) {
    return _memoryCache;
  }
  try {
    const raw = await AsyncStorage.getItem(ADMIN_CACHE_KEY);
    if (raw) {
      const parsed: AdminCacheData = JSON.parse(raw);
      if (Date.now() - parsed.timestamp < ADMIN_CACHE_TTL) {
        _memoryCache = parsed;
        return parsed;
      }
    }
  } catch { /* ignore */ }
  return null;
}

export async function setAdminCache(data: Partial<AdminCacheData>): Promise<void> {
  const existing = _memoryCache || { timestamp: Date.now() };
  const merged: AdminCacheData = {
    ...existing,
    ...data,
    timestamp: Date.now(),
  };
  _memoryCache = merged;
  try {
    await AsyncStorage.setItem(ADMIN_CACHE_KEY, JSON.stringify(merged));
  } catch { /* ignore */ }
}

export function clearAdminCache(): void {
  _memoryCache = null;
  AsyncStorage.removeItem(ADMIN_CACHE_KEY).catch(() => {});
}
