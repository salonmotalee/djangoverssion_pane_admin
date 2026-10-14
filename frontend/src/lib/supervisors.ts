import { isIranianPhone, latinDigits } from "./format.ts";
import type { Hall } from "./operations.ts";
import type { Paginated } from "./types.ts";

export type Supervisor = {
  id: number;
  first_name: string;
  last_name: string;
  phone: string;
  is_active: boolean;
  archived_at: string | null;
  halls: number[];
  hall_details: Pick<Hall, "id" | "name" | "is_active">[];
  created_at: string;
  updated_at: string;
};

export type SupervisorStatus = "active" | "inactive" | "archived";
export type SupervisorAction =
  | "archive"
  | "restore"
  | "activate"
  | "deactivate";

export const supervisorName = (supervisor: Supervisor) =>
  `${supervisor.first_name} ${supervisor.last_name}`.trim();

export const supervisorStatus = (supervisor: Supervisor): SupervisorStatus =>
  supervisor.archived_at
    ? "archived"
    : supervisor.is_active
      ? "active"
      : "inactive";

/** Canonical local mobile format, including Persian/Arabic digits. */
export function normalizeSupervisorPhone(value: string) {
  const phone = latinDigits(value).replace(/[\s-]/g, "");
  if (!isIranianPhone(phone)) return null;
  if (phone.startsWith("+98")) return `0${phone.slice(3)}`;
  if (phone.startsWith("0098")) return `0${phone.slice(4)}`;
  return phone;
}

/** Archived hall links are preserved by the API, never reassigned by the form. */
export const editableSupervisorHalls = (supervisor?: Supervisor) =>
  supervisor?.hall_details
    .filter((hall) => hall.is_active)
    .map((hall) => hall.id) || [];

/** The hall selector must include every page, even in organizations with >100 halls. */
export async function loadSupervisorHalls(
  request: (page: number) => Promise<Paginated<Hall>>,
) {
  const halls: Hall[] = [];
  let page = 1;
  let response: Paginated<Hall>;
  do {
    response = await request(page++);
    halls.push(...response.results);
  } while (response.next);
  return Array.from(new Map(halls.map((hall) => [hall.id, hall])).values());
}
