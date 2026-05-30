import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';
import AsyncStorage from '@react-native-async-storage/async-storage';

const QUEUE_KEY = 'agentos_offline_queue';

interface QueuedRequest {
  id: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
  timestamp: number;
}

interface OfflineContextType {
  isOnline: boolean;
  queueLength: number;
  enqueue: (req: Omit<QueuedRequest, 'id' | 'timestamp'>) => Promise<void>;
  flush: () => Promise<void>;
}

const OfflineContext = createContext<OfflineContextType>({
  isOnline: true,
  queueLength: 0,
  enqueue: async () => {},
  flush: async () => {},
});

async function loadQueue(): Promise<QueuedRequest[]> {
  try {
    const raw = await AsyncStorage.getItem(QUEUE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

async function saveQueue(queue: QueuedRequest[]): Promise<void> {
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}

export function OfflineProvider({ children }: { children: React.ReactNode }) {
  const [isOnline, setIsOnline] = useState(true);
  const [queueLength, setQueueLength] = useState(0);
  const queueRef = useRef<QueuedRequest[]>([]);
  const wasOfflineRef = useRef(false);

  useEffect(() => {
    loadQueue().then((q) => {
      queueRef.current = q;
      setQueueLength(q.length);
    });

    const unsubscribe = NetInfo.addEventListener((state: NetInfoState) => {
      const online = state.isConnected ?? true;
      setIsOnline(online);

      if (online && wasOfflineRef.current && queueRef.current.length > 0) {
        flushQueue();
      }
      wasOfflineRef.current = !online;
    });

    return () => unsubscribe();
  }, []);

  const flushQueue = useCallback(async () => {
    const queue = [...queueRef.current];
    const remaining: QueuedRequest[] = [];

    for (const req of queue) {
      try {
        await fetch(req.url, {
          method: req.method,
          headers: req.headers,
          body: req.body,
        });
      } catch {
        remaining.push(req);
      }
    }

    queueRef.current = remaining;
    setQueueLength(remaining.length);
    await saveQueue(remaining);
  }, []);

  const enqueue = useCallback(async (req: Omit<QueuedRequest, 'id' | 'timestamp'>) => {
    const item: QueuedRequest = {
      ...req,
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      timestamp: Date.now(),
    };
    queueRef.current.push(item);
    setQueueLength(queueRef.current.length);
    await saveQueue(queueRef.current);
  }, []);

  const flush = useCallback(async () => {
    await flushQueue();
  }, [flushQueue]);

  return (
    <OfflineContext.Provider value={{ isOnline, queueLength, enqueue, flush }}>
      {children}
    </OfflineContext.Provider>
  );
}

export function useOffline() {
  return useContext(OfflineContext);
}
