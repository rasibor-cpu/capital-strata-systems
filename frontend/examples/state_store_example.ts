import { create } from "zustand";

type DashboardSectionMap = Record<string, unknown>;

type DashboardSnapshot = {
  message_type: "dashboard_snapshot";
  payload_version: string;
  generated_at: string;
  sequence?: number;
  stale_after_ms?: number;
  sections: DashboardSectionMap;
};

type DashboardDelta = {
  message_type: "dashboard_delta" | "dashboard_heartbeat";
  payload_version: string;
  generated_at?: string;
  sequence: number;
  stale_after_ms?: number;
  changed_sections: string[];
  data: DashboardSectionMap;
};

type DashboardMessage = DashboardSnapshot | DashboardDelta;

type ConnectionState = "idle" | "connecting" | "open" | "stale" | "closed";

type CssDashboardStore = {
  connectionState: ConnectionState;
  sequence: number;
  lastUpdatedAt: string;
  staleAfterMs: number;
  sections: DashboardSectionMap;
  hydrate: (snapshot: DashboardSnapshot) => void;
  applyDelta: (delta: DashboardDelta) => void;
  markConnection: (state: ConnectionState) => void;
  markStaleIfExpired: () => void;
};

export const useCssDashboardStore = create<CssDashboardStore>((set, get) => ({
  connectionState: "idle",
  sequence: 0,
  lastUpdatedAt: "",
  staleAfterMs: 15000,
  sections: {},

  hydrate: (snapshot) =>
    set({
      connectionState: "open",
      sequence: snapshot.sequence ?? 0,
      lastUpdatedAt: snapshot.generated_at,
      staleAfterMs: snapshot.stale_after_ms ?? 15000,
      sections: snapshot.sections,
    }),

  applyDelta: (delta) => {
    if (delta.sequence <= get().sequence) return;

    if (delta.message_type === "dashboard_heartbeat") {
      set({
        connectionState: "open",
        sequence: delta.sequence,
        lastUpdatedAt: delta.generated_at ?? new Date().toISOString(),
        staleAfterMs: delta.stale_after_ms ?? get().staleAfterMs,
      });
      return;
    }

    set((state) => ({
      connectionState: "open",
      sequence: delta.sequence,
      lastUpdatedAt: delta.generated_at ?? new Date().toISOString(),
      staleAfterMs: delta.stale_after_ms ?? state.staleAfterMs,
      sections: {
        ...state.sections,
        ...delta.data,
      },
    }));
  },

  markConnection: (connectionState) => set({ connectionState }),

  markStaleIfExpired: () => {
    const lastUpdatedAt = get().lastUpdatedAt;
    if (!lastUpdatedAt) return;

    const ageMs = Date.now() - new Date(lastUpdatedAt).getTime();
    if (ageMs > get().staleAfterMs) {
      set({ connectionState: "stale" });
    }
  },
}));

export function connectCssDashboardSocket(url = "/ws/v1/dashboard-state") {
  let socket: WebSocket | undefined;
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  let closedByCaller = false;

  const connect = () => {
    useCssDashboardStore.getState().markConnection("connecting");
    socket = new WebSocket(url);

    socket.onopen = () => {
      useCssDashboardStore.getState().markConnection("open");
    };

    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as DashboardMessage;

      if (message.message_type === "dashboard_snapshot") {
        useCssDashboardStore.getState().hydrate(message);
        return;
      }

      useCssDashboardStore.getState().applyDelta(message);
    };

    socket.onclose = () => {
      useCssDashboardStore.getState().markConnection("closed");
      if (closedByCaller) return;
      reconnectTimer = setTimeout(connect, 1500);
    };

    socket.onerror = () => {
      socket?.close();
    };
  };

  connect();

  const staleTimer = setInterval(() => {
    useCssDashboardStore.getState().markStaleIfExpired();
  }, 1000);

  return () => {
    closedByCaller = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    clearInterval(staleTimer);
    socket?.close();
  };
}
