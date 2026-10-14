export type TicketStatus =
  | "open"
  | "awaiting_support"
  | "awaiting_customer"
  | "resolved"
  | "closed";
export type TicketPriority = "low" | "normal" | "high" | "urgent";
export type TicketCategory = "general" | "technical" | "billing" | "account";
export type SupportStaff = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
};
export type SupportStatusEvent = {
  id: number;
  previous_status: TicketStatus | "";
  status: TicketStatus;
  actor_name: string;
  created_at: string;
};
export type SupportTicket = {
  id: number;
  subject: string;
  category: TicketCategory;
  priority: TicketPriority;
  status: TicketStatus;
  organization: { id: number; name: string; slug: string };
  assigned_to: SupportStaff | null;
  created_at: string;
  updated_at: string;
  unread_count: number;
  last_message_preview: string;
  can_reply?: boolean;
  can_resolve?: boolean;
  can_close?: boolean;
  can_reopen?: boolean;
  can_assign?: boolean;
  status_history?: SupportStatusEvent[];
  status_history_count?: number;
};
export type SupportMessage = {
  id: number;
  body: string;
  author_name: string;
  author_role: string;
  created_at: string;
  is_mine: boolean;
};
export type SupportNotification = {
  id: number;
  ticket_id: number;
  subject: string;
  kind: string;
  body: string;
  created_at: string;
  is_read: boolean;
};
export type SupportNotifications = {
  unread_count: number;
  unread_messages: number;
  open_tickets: number;
  awaiting_support: number;
  awaiting_customer: number;
  items: SupportNotification[];
};

export const ticketStatuses: Record<TicketStatus, string> = {
  open: "باز",
  awaiting_support: "منتظر پاسخ پشتیبانی",
  awaiting_customer: "منتظر پاسخ مجموعه",
  resolved: "حل‌شده",
  closed: "بسته‌شده",
};
export const ticketPriorities: Record<TicketPriority, string> = {
  low: "کم",
  normal: "معمولی",
  high: "زیاد",
  urgent: "فوری",
};
export const ticketCategories: Record<TicketCategory, string> = {
  general: "عمومی",
  technical: "فنی",
  billing: "مالی و اشتراک",
  account: "حساب و دسترسی",
};

export function supportPrefix(slug?: string) {
  return slug
    ? `organizations/${encodeURIComponent(slug)}/support/`
    : "support/";
}
export function supportHref(slug?: string, ticketId?: number) {
  const base = slug ? `/${encodeURIComponent(slug)}/support` : "/support";
  return ticketId === undefined ? base : `${base}/${ticketId}`;
}
export function ticketNeedsReopen(status: TicketStatus) {
  return status === "resolved" || status === "closed";
}

/** A newly received event changes only its conversation, not every open ticket. */
export function ticketNotificationRevision(
  items: SupportNotification[],
  ticketId: number,
) {
  return items
    .filter((item) => item.ticket_id === ticketId)
    .sort((left, right) => left.id - right.id)
    .map((item) => `${item.id}:${item.kind}`)
    .join(",");
}

/** The conversation requests newest-first pages and renders each chronologically. */
export function chronologicalMessages(messages: SupportMessage[]) {
  return [...messages].sort(
    (left, right) =>
      left.created_at.localeCompare(right.created_at) || left.id - right.id,
  );
}
