"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Check,
  CheckCheck,
  Clock3,
  History,
  ListChecks,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { api, mutate } from "@/lib/api";
import { date, number, queryString, time } from "@/lib/format";
import { clockTime, type Hall, type StudySession } from "@/lib/operations";
import { todayTehran } from "@/lib/scheduling";
import { loadSupervisorHalls } from "@/lib/supervisors";
import type { Paginated } from "@/lib/types";
import { useData } from "@/lib/use-data";
import { HelpTooltip } from "./help-tooltip";
import {
  DateField,
  Empty,
  ErrorState,
  Field,
  InlineError,
  Modal,
  PageHeading,
  Spinner,
} from "./ui";
import "./scheduling.css";
type AttendanceStatus = "present" | "absent" | "late";
const statuses: Record<AttendanceStatus, string> = {
  present: "حاضر",
  absent: "غایب",
  late: "تأخیر",
};
type AttendanceAudit = {
  id: number;
  actor_name: string;
  original_recorder_name: string;
  previous: { status: AttendanceStatus };
  new: { status: AttendanceStatus };
  reason: string;
  created_at: string;
};
type AttendanceRecord = {
  id: number;
  status: AttendanceStatus;
  source: "manual" | "automatic";
  revision: number;
  created_at: string;
  updated_at: string;
  recorder: { id: number; name: string };
  early_departure: boolean;
  departed_at: string | null;
  can_edit: boolean;
  audit?: AttendanceAudit[];
};
type RosterStudent = {
  id: number;
  identifier: string;
  first_name: string;
  last_name: string;
  record: AttendanceRecord | null;
};
type ManagerRoster = {
  hall: number;
  date: string;
  sessions: StudySession[];
  session: number | null;
  starts_at: string | null;
  ends_at: string | null;
  provisional: boolean;
  students: RosterStudent[];
};

function useManagerHalls(slug: string) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    slug: string;
    revision: number;
    data: Hall[];
    error: string | null;
  } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    loadSupervisorHalls((page) =>
      api<Paginated<Hall>>(
        `organizations/${slug}/halls/?${queryString({ status: "all", page_size: 100, page })}`,
        { signal: controller.signal },
      ),
    )
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ slug, revision, data, error: null });
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted)
          setState({ slug, revision, data: [], error: error.message });
      });
    return () => controller.abort();
  }, [slug, revision]);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  return {
    data: state?.slug === slug ? state.data : null,
    error: state?.slug === slug ? state.error : null,
    loading: state?.slug !== slug || state.revision !== revision,
    refresh,
  };
}

export function ManagerAttendance({ slug }: { slug: string }) {
  const halls = useManagerHalls(slug);
  const [selectedHall, setSelectedHall] = useState("");
  const [day, setDay] = useState(todayTehran);
  const [session, setSession] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const hall = selectedHall || String(halls.data?.[0]?.id || "");
  const rosterKey = `${hall}:${day}:${session}`;
  const state = useData<ManagerRoster>(
    hall && day
      ? `organizations/${slug}/attendance/?${queryString({ hall, date: day, session })}`
      : null,
  );
  const [draft, setDraft] = useState<{
    key: string;
    changes: Record<number, AttendanceStatus>;
  }>({ key: "", changes: {} });
  const [correction, setCorrection] = useState(false);
  const [history, setHistory] = useState<RosterStudent | null>(null);
  const [saved, setSaved] = useState(false);
  const students = useMemo(() => state.data?.students || [], [state.data]);
  const changes = draft.key === rosterKey ? draft.changes : {};
  const dirty = students.filter(
    (student) =>
      student.record &&
      changes[student.record.id] &&
      changes[student.record.id] !== student.record.status,
  );
  const filtered = useMemo(
    () =>
      students.filter((student) =>
        `${student.first_name} ${student.last_name} ${student.identifier}`.includes(
          search.trim(),
        ),
      ),
    [students, search],
  );
  const counts = students.reduce(
    (totals, student) => {
      if (student.record) totals[student.record.status]++;
      else totals.pending++;
      return totals;
    },
    { present: 0, absent: 0, late: 0, pending: 0 },
  );
  const totalPages = Math.max(1, Math.ceil(filtered.length / 50));
  const displayedPage = Math.min(page, totalPages);
  function changeStatus(records: RosterStudent[], status: AttendanceStatus) {
    setDraft((current) => {
      const next = current.key === rosterKey ? { ...current.changes } : {};
      for (const student of records)
        if (student.record) next[student.record.id] = status;
      return { key: rosterKey, changes: next };
    });
    setSaved(false);
  }
  function switchScope() {
    setDraft({ key: "", changes: {} });
    setPage(1);
    setSaved(false);
  }
  return (
    <div className="manager-attendance schedule-page">
      <PageHeading
        eyebrow="نظارت دقیق، تصمیم مطمئن"
        title="نظارت بر حضور و غیاب"
      >
        <HelpTooltip
          label="راهنمای اصلاح حضور و غیاب"
          content="مدیر می‌تواند رکوردهای سالن‌های مجموعه را در هر زمان اصلاح کند. ثبت دلیل الزامی است و مالک اصلی، زمان ایجاد و سابقهٔ تغییرات حفظ می‌شوند."
        />
        <span className="schedule-manager-label">
          <ShieldCheck size={16} />
          دسترسی مدیر
        </span>
      </PageHeading>
      {saved && (
        <div className="schedule-success" role="status">
          <CheckCheck size={19} />
          اصلاحات با حفظ مالک اصلی و ثبت سابقه ذخیره شدند.
        </div>
      )}
      <div className="attendance-scope">
        <Field label="سالن">
          <select
            aria-label="سالن حضور و غیاب"
            value={hall}
            onChange={(event) => {
              setSelectedHall(event.target.value);
              setSession("");
              switchScope();
            }}
            disabled={halls.loading}
          >
            <option value="">انتخاب سالن</option>
            {halls.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
                {!item.is_active && " · غیرفعال"}
              </option>
            ))}
          </select>
        </Field>
        <DateField
          label="تاریخ حضور و غیاب"
          value={day}
          required
          onChange={(value) => {
            setDay(value);
            switchScope();
          }}
        />
        <Field label="پارت مطالعاتی">
          <select
            aria-label="پارت حضور و غیاب"
            value={session}
            onChange={(event) => {
              setSession(event.target.value);
              switchScope();
            }}
            disabled={!state.data?.sessions.length || state.loading}
          >
            <option value="">انتخاب پارت</option>
            {state.data?.sessions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title} · {clockTime(item.start_time)}–
                {clockTime(item.end_time)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {halls.error ? (
        <ErrorState error={halls.error} retry={halls.refresh} />
      ) : !hall ? (
        <Empty
          title="سالنی برای نمایش نیست"
          description="ابتدا سالن‌های مجموعه را ثبت کنید."
        />
      ) : state.error ? (
        <ErrorState error={state.error} retry={state.refresh} />
      ) : state.loading ? (
        <Spinner label="در حال دریافت سوابق…" />
      ) : !session ? (
        <Empty
          title="پارت مورد نظر را انتخاب کنید"
          description="سالن، تاریخ شمسی و پارت را برای مرور حضور و غیاب انتخاب کنید."
        />
      ) : !students.length ? (
        <Empty
          title="رکوردی برای این پارت نیست"
          description="پس از ثبت حضور و غیاب مراقب، رکوردها در اینجا نمایش داده می‌شوند."
        />
      ) : (
        <>
          <div className="attendance-overview">
            {(["present", "late", "absent"] as const).map((status) => (
              <div className={`attendance-count ${status}`} key={status}>
                <span>{statuses[status]}</span>
                <strong>{number(counts[status])}</strong>
              </div>
            ))}
            <div className="attendance-count pending">
              <span>ثبت‌نشده</span>
              <strong>{number(counts.pending)}</strong>
            </div>
          </div>
          <div className="attendance-toolbar">
            <label className="schedule-search">
              <Search size={17} />
              <input
                aria-label="جست‌وجوی دانش‌آموز برای اصلاح حضور و غیاب"
                placeholder="نام یا شناسهٔ دانش‌آموز…"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
              />
            </label>
            <div className="attendance-batch">
              <span>اعمال به نتایج:</span>
              {(["present", "late", "absent"] as const).map((status) => (
                <button
                  key={status}
                  className={`attendance-status-button ${status}`}
                  onClick={() => changeStatus(filtered, status)}
                >
                  {statuses[status]}
                </button>
              ))}
            </div>
          </div>
          <div className="attendance-table-scroll">
            <table className="attendance-table">
              <caption className="sr-only">
                حضور و غیاب دانش‌آموزان و سابقهٔ ثبت اولیه
              </caption>
              <thead>
                <tr>
                  <th>دانش‌آموز</th>
                  <th>وضعیت</th>
                  <th>ثبت‌کننده / زمان</th>
                  <th>خروج زودهنگام</th>
                  <th>سابقه</th>
                </tr>
              </thead>
              <tbody>
                {filtered
                  .slice((displayedPage - 1) * 50, displayedPage * 50)
                  .map((student) => {
                    const record = student.record;
                    const status = record
                      ? changes[record.id] || record.status
                      : null;
                    const isDirty = record && status !== record.status;
                    return (
                      <tr
                        key={student.id}
                        className={isDirty ? "attendance-row-dirty" : ""}
                      >
                        <td>
                          <div className="attendance-student">
                            <span className="schedule-avatar">
                              {student.first_name.slice(0, 1)}
                            </span>
                            <span>
                              <strong>
                                {student.first_name} {student.last_name}
                              </strong>
                              <small>{student.identifier}</small>
                            </span>
                          </div>
                        </td>
                        <td>
                          {record ? (
                            <div
                              className="attendance-status-controls"
                              role="group"
                              aria-label={`وضعیت ${student.first_name} ${student.last_name}`}
                            >
                              {(["present", "late", "absent"] as const).map(
                                (value) => (
                                  <button
                                    key={value}
                                    className={`attendance-status-button ${value} ${status === value ? "selected" : ""}`}
                                    aria-pressed={status === value}
                                    onClick={() =>
                                      changeStatus([student], value)
                                    }
                                  >
                                    {status === value && <Check size={12} />}
                                    {statuses[value]}
                                  </button>
                                ),
                              )}
                            </div>
                          ) : (
                            <span className="schedule-muted">
                              هنوز ثبت نشده
                            </span>
                          )}
                          {isDirty && (
                            <small className="attendance-change-label">
                              {statuses[record!.status]} <ArrowLeft size={12} />{" "}
                              {statuses[status!]}
                            </small>
                          )}
                        </td>
                        <td>
                          {record ? (
                            <>
                              <strong>{record.recorder.name}</strong>
                              <small>
                                {date(record.created_at)} ·{" "}
                                {time(record.created_at)}
                              </small>
                              <span
                                className={`schedule-diff ${record.source === "automatic" ? "new" : "existing"}`}
                              >
                                {record.source === "automatic"
                                  ? "هوشمند"
                                  : "دستی"}
                              </span>
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>
                          {record?.early_departure ? (
                            <span className="attendance-early">
                              <Clock3 size={14} />
                              {record.departed_at
                                ? time(record.departed_at)
                                : "خروج زودهنگام"}
                            </span>
                          ) : (
                            <span className="schedule-muted">—</span>
                          )}
                        </td>
                        <td>
                          <button
                            className="icon-button"
                            aria-label={`سابقهٔ حضور و غیاب ${student.first_name} ${student.last_name}`}
                            onClick={() => setHistory(student)}
                            disabled={!record}
                          >
                            <History size={18} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
            {!filtered.length && (
              <p className="schedule-muted">
                دانش‌آموزی مطابق جست‌وجو پیدا نشد.
              </p>
            )}
          </div>
          {totalPages > 1 && (
            <div className="schedule-pagination">
              <button
                className="button secondary compact"
                disabled={displayedPage <= 1}
                onClick={() => setPage(displayedPage - 1)}
              >
                قبلی
              </button>
              <span>
                {number(displayedPage)} از {number(totalPages)} ·{" "}
                {number(filtered.length)} دانش‌آموز
              </span>
              <button
                className="button secondary compact"
                disabled={displayedPage >= totalPages}
                onClick={() => setPage(displayedPage + 1)}
              >
                بعدی
              </button>
            </div>
          )}
          {dirty.length > 0 && (
            <div className="attendance-savebar">
              <div>
                <ListChecks size={21} />
                <strong>{number(dirty.length)} اصلاح آمادهٔ ثبت</strong>
              </div>
              <button
                className="button secondary"
                onClick={() => setDraft({ key: rosterKey, changes: {} })}
              >
                بازگردانی
              </button>
              <button
                className="button primary"
                onClick={() => setCorrection(true)}
              >
                <CheckCheck size={18} />
                ثبت اصلاحات
              </button>
            </div>
          )}
        </>
      )}
      {correction && (
        <CorrectionDialog
          slug={slug}
          students={dirty}
          changes={changes}
          onClose={() => setCorrection(false)}
          onSaved={() => {
            setCorrection(false);
            setDraft({ key: rosterKey, changes: {} });
            setSaved(true);
            state.refresh();
          }}
        />
      )}
      {history?.record && (
        <AttendanceHistory student={history} onClose={() => setHistory(null)} />
      )}
    </div>
  );
}
function CorrectionDialog({
  slug,
  students,
  changes,
  onClose,
  onSaved,
}: {
  slug: string;
  students: RosterStudent[];
  changes: Record<number, AttendanceStatus>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal
      title="ثبت اصلاحات مدیر"
      description="مالک اصلی رکورد و مهلت ویرایش مراقب حفظ می‌شوند."
      onClose={() => !pending && onClose()}
    >
      <form
        className="schedule-editor"
        onSubmit={async (event) => {
          event.preventDefault();
          if (reason.trim().length < 3) {
            setError("دلیل کوتاهی برای اصلاح وارد کنید.");
            return;
          }
          setPending(true);
          setError(null);
          try {
            await mutate(
              `organizations/${slug}/attendance/corrections/`,
              "POST",
              {
                records: students.map((student) => ({
                  id: student.record!.id,
                  status: changes[student.record!.id],
                  revision: student.record!.revision,
                })),
                reason: reason.trim(),
              },
            );
            onSaved();
          } catch (failure) {
            setError((failure as Error).message);
          } finally {
            setPending(false);
          }
        }}
      >
        <InlineError message={error} />
        <div className="attendance-correction-list">
          {students.map((student) => (
            <div key={student.id}>
              <span>
                {student.first_name} {student.last_name}
              </span>
              <span className={`schedule-diff ${student.record!.status}`}>
                {statuses[student.record!.status]}
              </span>
              <ArrowLeft size={14} />
              <span className={`schedule-diff ${changes[student.record!.id]}`}>
                {statuses[changes[student.record!.id]]}
              </span>
            </div>
          ))}
        </div>
        <Field
          label="دلیل اصلاح"
          required
          hint="این دلیل همراه نام مدیر و مقدار قبل و بعد در سابقه ثبت می‌شود."
        >
          <textarea
            name="reason"
            aria-label="دلیل اصلاح حضور و غیاب"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            required
            minLength={3}
            maxLength={500}
            rows={3}
            placeholder="مثلاً بررسی دوبارهٔ گزارش ورود دانش‌آموز"
            disabled={pending}
          />
        </Field>
        <div className="schedule-dialog-footer">
          <span>{number(students.length)} رکورد</span>
          <button
            className="button primary"
            type="submit"
            disabled={pending || reason.trim().length < 3}
          >
            <ShieldCheck size={17} />
            {pending ? "در حال ثبت…" : "تأیید اصلاحات"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
function AttendanceHistory({
  student,
  onClose,
}: {
  student: RosterStudent;
  onClose: () => void;
}) {
  const record = student.record!;
  return (
    <Modal
      title={`سابقهٔ ${student.first_name} ${student.last_name}`}
      onClose={onClose}
    >
      <div className="attendance-history">
        <div className="attendance-original">
          <UserRound size={23} />
          <div>
            <strong>ثبت اولیه توسط {record.recorder.name}</strong>
            <small>
              {date(record.created_at)} · {time(record.created_at)}
            </small>
            <small>مالک اصلی رکورد · نسخهٔ {number(record.revision)}</small>
          </div>
        </div>
        {record.early_departure && (
          <p className="attendance-early">
            <Clock3 size={16} />
            خروج زودهنگام:{" "}
            {record.departed_at
              ? `${date(record.departed_at)} · ${time(record.departed_at)}`
              : "ثبت شده"}
          </p>
        )}
        {record.audit?.length ? (
          <ol className="attendance-audit-list">
            {record.audit.map((entry) => (
              <li key={entry.id}>
                <span className="attendance-audit-dot">
                  <History size={13} />
                </span>
                <div>
                  <strong>{entry.actor_name}</strong>
                  <small>
                    {date(entry.created_at)} · {time(entry.created_at)}
                  </small>
                  <p>
                    {entry.previous?.status
                      ? statuses[entry.previous.status]
                      : "ثبت اولیه"}{" "}
                    ← {entry.new?.status ? statuses[entry.new.status] : "—"}
                  </p>
                  {entry.reason && <blockquote>{entry.reason}</blockquote>}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="schedule-muted">
            هنوز اصلاحی برای این رکورد ثبت نشده است.
          </p>
        )}
      </div>
    </Modal>
  );
}
