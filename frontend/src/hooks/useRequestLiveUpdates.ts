import { useEffect, useRef } from "react";
import { getAccessToken } from "../lib/storage";

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

/**
 * Live updates via SSE (fetch stream + Bearer) with interval polling fallback.
 */
export function useRequestLiveUpdates(
  requestId: string | undefined,
  onTick: () => void | Promise<void>,
  options: { enabled: boolean },
) {
  const onTickRef = useRef(onTick);
  onTickRef.current = onTick;

  useEffect(() => {
    if (!options.enabled || !requestId) return;

    let cancelled = false;
    let pollTimer: number | undefined;
    const abort = new AbortController();

    function startPolling() {
      if (pollTimer !== undefined) return;
      pollTimer = window.setInterval(() => {
        void onTickRef.current();
      }, 3000);
    }

    async function startSse() {
      const token = getAccessToken();
      if (!token) {
        startPolling();
        return;
      }
      try {
        const response = await fetch(`${API_BASE}/api/v1/requests/${requestId}/events`, {
          headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
          signal: abort.signal,
        });
        if (!response.ok || !response.body) {
          startPolling();
          return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";
          for (const chunk of parts) {
            if (chunk.includes("event: update") || chunk.includes("event: snapshot") || chunk.includes("event: done")) {
              void onTickRef.current();
            }
            if (chunk.includes("event: done")) {
              cancelled = true;
              abort.abort();
              return;
            }
          }
        }
        if (!cancelled) startPolling();
      } catch {
        if (!cancelled) startPolling();
      }
    }

    // Poll immediately + open SSE
    void onTickRef.current();
    startPolling();
    void startSse();

    return () => {
      cancelled = true;
      abort.abort();
      if (pollTimer !== undefined) window.clearInterval(pollTimer);
    };
  }, [requestId, options.enabled]);
}
