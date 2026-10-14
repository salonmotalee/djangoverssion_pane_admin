import assert from "node:assert/strict";
import test from "node:test";
import { ApiError } from "../src/lib/api.ts";
import {
  createSupportNotificationStore,
  emptySupportNotifications,
} from "../src/lib/support-notifications.ts";
import type { SupportNotifications } from "../src/lib/support.ts";

function notifications(unread: number): SupportNotifications {
  return {
    unread_count: unread,
    unread_messages: unread,
    open_tickets: 1,
    awaiting_support: 1,
    awaiting_customer: 0,
    items: [],
  };
}

function harness(initiallyVisible = true) {
  let visible = initiallyVisible;
  let visibilityListener = () => {};
  let tick = () => {};
  let cancelledTimers = 0;
  let removedListeners = 0;
  const calls: {
    signal: AbortSignal;
    resolve: (data: SupportNotifications) => void;
    reject: (error: Error) => void;
  }[] = [];
  const store = createSupportNotificationStore(
    "support/",
    (path, signal) => {
      assert.equal(path, "support/notifications/");
      return new Promise<SupportNotifications>((resolve, reject) => {
        calls.push({ signal, resolve, reject });
      });
    },
    {
      visible: () => visible,
      listen: (listener) => {
        visibilityListener = listener;
        return () => {
          removedListeners++;
        };
      },
      schedule: (callback, delay) => {
        assert.equal(delay, 25_000);
        tick = callback;
        return () => {
          cancelledTimers++;
        };
      },
    },
  );
  return {
    store,
    calls,
    tick: () => tick(),
    setVisible: (value: boolean) => {
      visible = value;
      visibilityListener();
    },
    cleanupCounts: () => ({ cancelledTimers, removedListeners }),
  };
}

test("post-write invalidation wins a delayed pre-write GET, with shared polling deduplicated", async () => {
  const { store, calls } = harness();
  let renders = 0;
  const unsubscribeBell = store.subscribe(() => {
    renders++;
  });
  const unsubscribeDashboard = store.subscribe(() => {
    renders++;
  });
  assert.equal(calls.length, 1, "Multiple consumers must share their GET");
  const preWrite = store.refresh();
  assert.equal(
    store.refresh(),
    preWrite,
    "Polling must reuse an in-flight GET",
  );
  const postWrite = store.invalidate();
  assert.equal(calls.length, 2);
  assert.equal(calls[0].signal.aborted, true);
  calls[1].resolve(notifications(0));
  await postWrite;
  assert.equal(store.getSnapshot().data?.unread_count, 0);
  calls[0].resolve(notifications(9));
  await preWrite;
  assert.equal(
    store.getSnapshot().data?.unread_count,
    0,
    "A late old GET must never restore stale unread data",
  );
  assert.equal(
    renders,
    2,
    "Only the authoritative response notifies both consumers",
  );
  unsubscribeBell();
  assert.ok(
    store.getSnapshot().data,
    "Remaining consumers retain their current snapshot",
  );
  unsubscribeDashboard();
  assert.equal(
    store.getSnapshot(),
    emptySupportNotifications,
    "Logout clears recipient data",
  );
});

test("hidden pages make no polling requests, visibility resumes and unmount aborts and cleans up", async () => {
  const { store, calls, tick, setVisible, cleanupCounts } = harness(false);
  const unsubscribe = store.subscribe(() => {});
  tick();
  await store.refresh();
  assert.equal(calls.length, 0);
  setVisible(true);
  assert.equal(calls.length, 1);
  tick();
  assert.equal(
    calls.length,
    1,
    "A visibility refresh and timer tick must deduplicate",
  );
  const pending = store.refresh();
  unsubscribe();
  assert.equal(calls[0].signal.aborted, true);
  assert.deepEqual(cleanupCounts(), {
    cancelledTimers: 1,
    removedListeners: 1,
  });
  calls[0].resolve(notifications(4));
  await pending;
  assert.equal(
    store.getSnapshot(),
    emptySupportNotifications,
    "An unmounted response cannot repopulate another session's cache",
  );
});

test("permission revocation discards private cached events and stops automatic polling", async () => {
  const { store, calls, cleanupCounts } = harness();
  const unsubscribe = store.subscribe(() => {});
  const initial = store.refresh();
  calls[0].resolve(notifications(7));
  await initial;
  assert.equal(store.getSnapshot().data?.unread_count, 7);
  const revoked = store.invalidate();
  calls[1].reject(new ApiError("دسترسی پشتیبانی لغو شده است.", 403));
  await revoked;
  assert.equal(store.getSnapshot().data, null);
  assert.equal(store.getSnapshot().error, "دسترسی پشتیبانی لغو شده است.");
  assert.equal(cleanupCounts().cancelledTimers, 1);
  unsubscribe();
  assert.deepEqual(cleanupCounts(), {
    cancelledTimers: 1,
    removedListeners: 1,
  });
});
