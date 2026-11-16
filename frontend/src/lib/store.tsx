import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, get } from './api';
import type { Me } from './types';

interface Store {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<Me | null>;
  toast: (msg: string, kind?: 'ok' | 'err') => void;
}

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind: 'ok' | 'err' }[]>([]);

  const refresh = useCallback(async () => {
    try {
      const m = await get<Me>('/me');
      setMe(m);
      return m;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setMe(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const toast = useCallback((msg: string, kind: 'ok' | 'err' = 'ok') => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(() => ({ me, loading, refresh, toast }), [me, loading, refresh, toast]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            {t.msg}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error('StoreProvider 밖에서 호출');
  return s;
}

export function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : '문제가 생겼어요';
}
