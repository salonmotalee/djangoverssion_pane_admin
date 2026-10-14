import { api, ApiError } from "./api.ts";
import type { SupportNotifications } from "./support.ts";

export type SupportNotificationSnapshot = {
  data: SupportNotifications | null;
  error: string | null;
  loading: boolean;
};
export const emptySupportNotifications: SupportNotificationSnapshot = {
  data: null,
  error: null,
  loading: true,
};
type NotificationEnvironment = {
  visible: () => boolean;
  listen: (callback: () => void) => () => void;
  schedule: (callback: () => void, delay: number) => () => void;
};
const browserEnvironment: NotificationEnvironment = {
  visible: () =>
    typeof document !== "undefined" && document.visibilityState !== "hidden",
  listen: (callback) => {
    document.addEventListener("visibilitychange", callback);
    return () => document.removeEventListener("visibilitychange", callback);
  },
  schedule: (callback, delay) => {
    const timer = setInterval(callback, delay);
    return () => clearInterval(timer);
  },
};

/** All views for a recipient share one visible-page timer and one GET. */
export function createSupportNotificationStore(
  prefix: string,
  fetchNotifications = (path: string, signal: AbortSignal) =>
    api<SupportNotifications>(path, { signal }),
  environment = browserEnvironment,
) {
  let snapshot = emptySupportNotifications;
  let controller: AbortController | null = null;
  let request: Promise<void> | null = null;
  let cancelTimer: (() => void) | null = null;
  let stopListening: (() => void) | null = null;
  const subscribers = new Set<() => void>();
  const emit = () => subscribers.forEach((listener) => listener());
  const refresh = () => {
    if (request) return request;
    if (!subscribers.size || !environment.visible()) return Promise.resolve();
    controller = new AbortController();
    const current = controller;
    request = fetchNotifications(`${prefix}notifications/`, current.signal)
      .then((data) => {
        if (current.signal.aborted) return;
        snapshot = { data, loading: false, error: null };
        emit();
      })
      .catch((error: Error) => {
        if (current.signal.aborted) return;
        const denied =
          error instanceof ApiError && [401, 403].includes(error.status);
        if (denied) {
          cancelTimer?.();
          cancelTimer = null;
        }
        snapshot = {
          ...snapshot,
          ...(denied ? { data: null } : {}),
          loading: false,
          error: error.message || "دریافت اعلان‌ها ناموفق بود.",
        };
        emit();
      })
      .finally(() => {
        if (controller === current) {
          request = null;
          controller = null;
        }
      });
    return request;
  };
  const invalidate = () => {
    // A GET started before a write cannot authoritatively describe that write.
    controller?.abort();
    controller = null;
    request = null;
    return refresh();
  };
  const subscribe = (listener: () => void) => {
    subscribers.add(listener);
    if (subscribers.size === 1) {
      stopListening = environment.listen(() => {
        if (environment.visible()) void refresh();
      });
      cancelTimer = environment.schedule(() => void refresh(), 25_000);
      void refresh();
    }
    return () => {
      subscribers.delete(listener);
      if (!subscribers.size) {
        cancelTimer?.();
        cancelTimer = null;
        stopListening?.();
        stopListening = null;
        controller?.abort();
        controller = null;
        request = null;
        // Never show a previous user's cached notifications after logout.
        snapshot = emptySupportNotifications;
      }
    };
  };
  return { subscribe, getSnapshot: () => snapshot, refresh, invalidate };
}
