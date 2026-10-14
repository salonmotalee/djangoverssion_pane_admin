import assert from "node:assert/strict";
import test from "node:test";
import {
  chronologicalMessages,
  supportHref,
  supportPrefix,
  ticketNeedsReopen,
  ticketNotificationRevision,
  type SupportMessage,
  type SupportNotification,
  type TicketStatus,
} from "../src/lib/support.ts";

test("support links and API scopes encode one tenant segment independently", () => {
  assert.equal(supportPrefix(), "support/");
  assert.equal(supportHref(undefined, 17), "/support/17");
  assert.equal(supportPrefix("hall-a"), "organizations/hall-a/support/");
  assert.equal(supportHref("hall-a", 17), "/hall-a/support/17");
  assert.equal(
    supportPrefix("hall/a?next=other"),
    "organizations/hall%2Fa%3Fnext%3Dother/support/",
  );
  assert.equal(supportHref("hall/a", 17), "/hall%2Fa/support/17");
});

test("resolved and closed conversations require reopening before composing", () => {
  for (const status of [
    "open",
    "awaiting_support",
    "awaiting_customer",
  ] as TicketStatus[])
    assert.equal(ticketNeedsReopen(status), false);
  assert.equal(ticketNeedsReopen("resolved"), true);
  assert.equal(ticketNeedsReopen("closed"), true);
});

test("a newest-first full chat page renders chronologically without losing recent replies", () => {
  const messages = Array.from({ length: 30 }, (_, index) => ({
    id: 65 - index,
    created_at: new Date(Date.UTC(2026, 9, 14, 8, 65 - index)).toISOString(),
    body: `message-${65 - index}`,
  })) as SupportMessage[];
  const displayed = chronologicalMessages(messages);
  assert.equal(displayed.length, 30);
  assert.equal(displayed[0].id, 36);
  assert.equal(
    displayed.at(-1)?.id,
    65,
    "The latest reply must appear at the bottom",
  );
  assert.equal(messages[0].id, 65, "Rendering must not mutate the API page");
  assert.deepEqual(
    chronologicalMessages([
      { id: 4, created_at: "2026-10-14T08:00:00Z" },
      { id: 3, created_at: "2026-10-14T08:00:00Z" },
    ] as SupportMessage[]).map((message) => message.id),
    [3, 4],
  );
});

test("only a new event on the open ticket triggers its conversation refresh", () => {
  const events = [
    { id: 1, ticket_id: 10, kind: "message", is_read: false },
  ] as SupportNotification[];
  const revision = ticketNotificationRevision(events, 10);
  assert.equal(
    ticketNotificationRevision(
      [
        ...events,
        { id: 2, ticket_id: 20, kind: "status" } as SupportNotification,
      ],
      10,
    ),
    revision,
  );
  assert.equal(
    ticketNotificationRevision(
      events.map((item) => ({ ...item, is_read: true })),
      10,
    ),
    revision,
    "Marking events read must not cause a polling feedback loop",
  );
  assert.notEqual(
    ticketNotificationRevision(
      [
        ...events,
        { id: 3, ticket_id: 10, kind: "status" } as SupportNotification,
      ],
      10,
    ),
    revision,
  );
  const sameEvents = [
    { id: 5, ticket_id: 10, kind: "message", is_read: true },
    { id: 4, ticket_id: 10, kind: "status", is_read: false },
  ] as SupportNotification[];
  assert.equal(
    ticketNotificationRevision(sameEvents, 10),
    ticketNotificationRevision([...sameEvents].reverse(), 10),
    "Unread-first notification sorting must not refetch an unchanged conversation",
  );
});
