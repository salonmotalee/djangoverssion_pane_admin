"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  CheckCheck,
  Clock3,
  Copy,
  Layers,
  Pencil,
  Plus,
  Search,
  Settings2,
  Sparkles,
  Trash2,
  Users,
} from "lucide-react";
import { api, mutate } from "@/lib/api";
import { date, number, queryString } from "@/lib/format";
import { clockTime } from "@/lib/operations";
import {
  assignmentConflictId,
  authorizedSupervisors,
  calendarWeek,
  initialPreviewChoices,
  jalaliMonth,
  moveDate,
  saturdayWeek,
  selectedScheduleConflicts,
  todayTehran,
  uniqueAssignments,
  validateShift,
  weekDays,
  type PreviewAction,
  type ProposedAssignment,
  type ScheduleAssignment,
  type SchedulePreview,
  type ScheduleWeek,
  type WorkShift,
} from "@/lib/scheduling";
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

const monthNames = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];
const actionLabels: Record<PreviewAction, string> = {
  add: "افزودن",
  preserve: "حفظ موجود",
  replace: "جایگزینی انتخابی",
  skip: "رد کردن",
};
type EditTarget = { hall: number; shift: number; dates: string[] };

export function Scheduling({ slug }: { slug: string }) {
  const [week, setWeek] = useState(() => saturdayWeek(todayTehran()));
  const [hall, setHall] = useState("");
  const [shift, setShift] = useState("");
  const [edit, setEdit] = useState<EditTarget | null>(null);
  const [shiftManager, setShiftManager] = useState(false);
  const [monthly, setMonthly] = useState(false);
  const [preview, setPreview] = useState<SchedulePreview | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState("");
  const state = useData<ScheduleWeek>(
    `organizations/${slug}/schedule/?${queryString({ week_start: week })}`,
  );
  const data = state.data;
  const days = calendarWeek(week);
  const assignmentMap = useMemo(() => {
    const map = new Map<string, ScheduleAssignment[]>();
    for (const assignment of data?.assignments || []) {
      const key = `${assignment.date}:${assignment.hall}:${assignment.shift}`;
      map.set(key, [...(map.get(key) || []), assignment]);
    }
    return map;
  }, [data]);
  const conflictIds = useMemo(
    () =>
      new Set(
        (data?.conflicts || []).flatMap((conflict) => [
          assignmentConflictId(conflict.left),
          assignmentConflictId(conflict.right),
        ]),
      ),
    [data],
  );
  async function requestPreview(
    path: "preview" | "copy-preview",
    body: unknown,
  ) {
    setPending(true);
    setError(null);
    setSaved("");
    try {
      const result = await mutate<SchedulePreview>(
        `organizations/${slug}/schedule/${path}/`,
        "POST",
        body,
      );
      setPreview(result);
      setEdit(null);
      setMonthly(false);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setPending(false);
    }
  }
  function changed(message: string) {
    setPreview(null);
    setSaved(message);
    state.refresh();
  }
  const visibleHalls =
    data?.halls.filter((item) => !hall || item.id === Number(hall)) || [];
  const visibleShifts =
    data?.shifts.filter(
      (item) => item.is_active && (!shift || item.id === Number(shift)),
    ) || [];
  const supervisorsCount = new Set(
    data?.assignments.map((item) => item.supervisor),
  ).size;
  const historical =
    data?.assignments.filter(
      (assignment) =>
        !data.halls.some((item) => item.id === assignment.hall) ||
        !data.shifts.some(
          (item) => item.id === assignment.shift && item.is_active,
        ),
    ) || [];
  return (
    <div className="schedule-page">
      <PageHeading eyebrow="تیم منظم، سالن آرام" title="برنامه‌ریزی شیفت‌ها">
        <HelpTooltip
          label="راهنمای برنامه‌ریزی"
          content="هر خانه یک سالن، شیفت و روز است. چند مراقب انتخاب کنید، تغییرات را پیش‌نمایش بگیرید و سپس ذخیره کنید. هم‌پوشانی فقط با تأیید و دلیل شما ثبت می‌شود."
        />
        <button
          className="button secondary"
          onClick={() => setShiftManager(true)}
        >
          <Settings2 size={17} />
          مدیریت شیفت‌ها
        </button>
        <button
          className="button primary"
          disabled={
            !data?.halls.length ||
            !data?.shifts.some((item) => item.is_active) ||
            pending
          }
          onClick={() =>
            setEdit({
              hall: data!.halls[0].id,
              shift: data!.shifts.find((item) => item.is_active)!.id,
              dates: days,
            })
          }
        >
          <Plus size={18} />
          برنامه‌ریزی گروهی
        </button>
      </PageHeading>
      <InlineError message={error} />
      {saved && (
        <div className="schedule-success" role="status">
          <CheckCheck size={20} />
          {saved}
        </div>
      )}
      <div className="schedule-weekbar">
        <div className="schedule-week-navigation">
          <button
            className="icon-button"
            aria-label="هفته قبل"
            onClick={() => setWeek(moveDate(week, -7))}
          >
            <ArrowRight size={19} />
          </button>
          <div>
            <strong>
              {date(week)}{" "}
              <span>تا {date(moveDate(week, 6), { year: undefined })}</span>
            </strong>
            <small>هفتهٔ کاری · شنبه تا جمعه</small>
          </div>
          <button
            className="icon-button"
            aria-label="هفته بعد"
            onClick={() => setWeek(moveDate(week, 7))}
          >
            <ArrowLeft size={19} />
          </button>
          <button
            className="button subtle compact"
            onClick={() => setWeek(saturdayWeek(todayTehran()))}
          >
            این هفته
          </button>
        </div>
        <DateField
          label="رفتن به هفتهٔ تاریخ"
          value={week}
          onChange={(value) => value && setWeek(saturdayWeek(value))}
        />
      </div>
      <div className="schedule-toolbar">
        <label className="schedule-select">
          <span>سالن</span>
          <select
            aria-label="فیلتر سالن"
            value={hall}
            onChange={(event) => setHall(event.target.value)}
          >
            <option value="">همهٔ سالن‌ها</option>
            {data?.halls.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="schedule-select">
          <span>شیفت</span>
          <select
            aria-label="فیلتر شیفت"
            value={shift}
            onChange={(event) => setShift(event.target.value)}
          >
            <option value="">همهٔ شیفت‌ها</option>
            {data?.shifts
              .filter((item) => item.is_active)
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
          </select>
        </label>
        <div className="schedule-copy-actions">
          <button
            className="button secondary"
            disabled={pending || !data}
            onClick={() =>
              requestPreview("copy-preview", {
                mode: "week",
                source_week: moveDate(week, -7),
                target_week: week,
              })
            }
          >
            <Copy size={17} />
            کپی هفتهٔ قبل
          </button>
          <button
            className="button secondary"
            disabled={pending || !data}
            onClick={() => setMonthly(true)}
          >
            <Sparkles size={17} />
            تکرار در ماه
          </button>
        </div>
      </div>
      {state.error ? (
        <ErrorState error={state.error} retry={state.refresh} />
      ) : state.loading || !data ? (
        <div className="schedule-loading">
          <Spinner label="در حال آماده‌سازی هفته…" />
          {[0, 1, 2].map((row) => (
            <div key={row} className="schedule-skeleton" />
          ))}
        </div>
      ) : !data.halls.length || !visibleShifts.length ? (
        <Empty
          title={
            !data.halls.length
              ? "ابتدا سالن خود را بسازید"
              : "یک شیفت برای شروع بسازید"
          }
          description="با تعریف شیفت و سالن، برنامهٔ هفتگی تیم در اینجا قرار می‌گیرد."
          action={
            <button
              className="button primary"
              onClick={() => setShiftManager(true)}
            >
              <Clock3 size={17} />
              مدیریت شیفت‌ها
            </button>
          }
        />
      ) : (
        <>
          <div className="schedule-stats">
            <span>
              <CalendarDays size={16} />
              <strong>{number(data.assignments.length)}</strong> نوبت کاری
            </span>
            <span>
              <Users size={16} />
              <strong>{number(supervisorsCount)}</strong> مراقب
            </span>
            <span
              className={data.conflicts.length ? "schedule-warning-text" : ""}
            >
              <AlertTriangle size={16} />
              <strong>{number(data.conflicts.length)}</strong> هم‌پوشانی
            </span>
          </div>
          <div
            className="schedule-matrix-scroll"
            tabIndex={0}
            aria-label="جدول برنامهٔ هفتگی؛ برای نمایش روزها به طرفین پیمایش کنید"
          >
            <table className="schedule-matrix">
              <caption className="sr-only">
                برنامهٔ هفتگی مراقبان به تفکیک سالن، شیفت و روز
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="schedule-rowhead">
                    سالن / شیفت
                  </th>
                  {days.map((day, index) => (
                    <th
                      scope="col"
                      key={day}
                      className={day === todayTehran() ? "today" : ""}
                    >
                      <span>{weekDays[index]}</span>
                      <strong>
                        {date(day, {
                          year: undefined,
                          month: "short",
                          day: "numeric",
                        })}
                      </strong>
                      {day === todayTehran() && <small>امروز</small>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleHalls.flatMap((item) =>
                  visibleShifts.map((workShift, shiftIndex) => (
                    <tr
                      key={`${item.id}:${workShift.id}`}
                      className={shiftIndex === 0 ? "schedule-hall-first" : ""}
                    >
                      <th scope="row" className="schedule-rowhead">
                        <span className="schedule-hall-name">{item.name}</span>
                        <strong>{workShift.name}</strong>
                        <small dir="ltr">
                          {clockTime(workShift.start_time)} —{" "}
                          {clockTime(workShift.end_time)}
                        </small>
                        <button
                          className="schedule-row-batch"
                          aria-label={`برنامه‌ریزی هفتهٔ ${item.name}، ${workShift.name}`}
                          onClick={() =>
                            setEdit({
                              hall: item.id,
                              shift: workShift.id,
                              dates: days,
                            })
                          }
                        >
                          <Layers size={13} />
                          کل هفته
                        </button>
                      </th>
                      {days.map((day) => {
                        const assigned =
                          assignmentMap.get(
                            `${day}:${item.id}:${workShift.id}`,
                          ) || [];
                        const conflict = assigned.some((assignment) =>
                          conflictIds.has(assignment.id),
                        );
                        return (
                          <td
                            key={day}
                            className={`${day === todayTehran() ? "today" : ""} ${conflict ? "has-conflict" : ""}`}
                          >
                            <button
                              className={`schedule-cell ${assigned.length ? "filled" : ""}`}
                              aria-label={`${item.name}، ${workShift.name}، ${date(day)}؛ ${assigned.length ? assigned.map((assignment) => assignment.supervisor_name).join("، ") : "بدون مراقب"}؛ ویرایش`}
                              onClick={() =>
                                setEdit({
                                  hall: item.id,
                                  shift: workShift.id,
                                  dates: [day],
                                })
                              }
                            >
                              {assigned.length ? (
                                <>
                                  {assigned.map((assignment) => (
                                    <span
                                      className="schedule-person"
                                      key={assignment.id}
                                    >
                                      <i>
                                        {assignment.supervisor_name.slice(0, 1)}
                                      </i>
                                      <span>
                                        {assignment.supervisor_name}
                                        {(assignment.start_time !==
                                          workShift.start_time ||
                                          assignment.end_time !==
                                            workShift.end_time ||
                                          assignment.shift_name !==
                                            workShift.name) && (
                                          <small
                                            className="schedule-snapshot-time"
                                            title="زمان ثبت‌شدهٔ این نوبت؛ ویرایش شیفت، برنامهٔ قبلی را تغییر نمی‌دهد."
                                          >
                                            {assignment.shift_name !==
                                              workShift.name &&
                                              `${assignment.shift_name} · `}
                                            {clockTime(assignment.start_time)}–
                                            {clockTime(assignment.end_time)}
                                          </small>
                                        )}
                                      </span>
                                      {conflictIds.has(assignment.id) && (
                                        <AlertTriangle
                                          size={13}
                                          aria-label="هم‌پوشانی"
                                        />
                                      )}
                                    </span>
                                  ))}
                                  <span className="schedule-cell-edit">
                                    <Pencil size={12} />
                                    ویرایش
                                  </span>
                                </>
                              ) : (
                                <span className="schedule-cell-add">
                                  <Plus size={19} />
                                  <small>افزودن مراقب</small>
                                </span>
                              )}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
          <div className="schedule-matrix-footer">
            <span>
              <i className="schedule-legend-dot" />
              برنامهٔ ثبت‌شده
            </span>
            <span>
              <i className="schedule-legend-dot warning" />
              هم‌پوشانی شیفت‌ها
            </span>
            <span>ساعت شیفت‌ها محدودیت ورود مراقبان نیست.</span>
          </div>
        </>
      )}
      {!state.loading && historical.length > 0 && (
        <section
          className="schedule-historical"
          aria-label="برنامه‌های ثبت‌شده با سالن یا شیفت غیرفعال"
        >
          <div className="schedule-preview-toolbar">
            <strong>برنامه‌های غیرفعال این هفته</strong>
            <HelpTooltip
              label="راهنمای برنامه‌های غیرفعال"
              content="این نوبت‌ها پیش از غیرفعال‌کردن شیفت یا سالن ثبت شده‌اند. زمان واقعی نوبت حفظ شده است؛ برای تغییر آن ابتدا شیفت یا سالن را فعال کنید. حذف فقط پس از مرور و تأیید انجام می‌شود."
            />
          </div>
          <div className="schedule-historical-list">
            {historical.map((assignment) => (
              <article key={assignment.id}>
                <div>
                  <strong>{assignment.supervisor_name}</strong>
                  <small>
                    {assignment.hall_name} · {assignment.shift_name} ·{" "}
                    {date(assignment.date)}
                  </small>
                  <small>
                    {clockTime(assignment.start_time)} تا{" "}
                    {clockTime(assignment.end_time)}
                  </small>
                </div>
                {conflictIds.has(assignment.id) && (
                  <AlertTriangle
                    size={17}
                    className="schedule-warning-text"
                    aria-label="هم‌پوشانی"
                  />
                )}
                <button
                  className="button secondary compact"
                  disabled={pending}
                  onClick={() =>
                    requestPreview("preview", {
                      assignments: [],
                      remove_ids: [assignment.id],
                    })
                  }
                >
                  <Trash2 size={14} />
                  بررسی حذف
                </button>
              </article>
            ))}
          </div>
        </section>
      )}
      {edit && data && (
        <AssignmentEditor
          data={data}
          target={edit}
          days={days}
          pending={pending}
          error={error}
          onClose={() => !pending && setEdit(null)}
          onPreview={(assignments, remove_ids) =>
            requestPreview("preview", { assignments, remove_ids })
          }
        />
      )}
      {monthly && (
        <MonthCopy
          week={week}
          pending={pending}
          error={error}
          onClose={() => !pending && setMonthly(false)}
          onPreview={(year, month) =>
            requestPreview("copy-preview", {
              mode: "month",
              source_week: week,
              jalali_year: year,
              jalali_month: month,
            })
          }
        />
      )}
      {preview && data && (
        <PreviewDialog
          slug={slug}
          preview={preview}
          data={data}
          onClose={() => setPreview(null)}
          onSaved={(count) =>
            changed(
              `${number(count)} نوبت افزوده شد؛ تغییرات برنامه ذخیره شدند.`,
            )
          }
        />
      )}
      {shiftManager && (
        <ShiftManager
          slug={slug}
          onClose={() => setShiftManager(false)}
          onChanged={state.refresh}
        />
      )}
    </div>
  );
}

function AssignmentEditor({
  data,
  target,
  days,
  pending,
  error,
  onClose,
  onPreview,
}: {
  data: ScheduleWeek;
  target: EditTarget;
  days: string[];
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onPreview: (rows: ProposedAssignment[], remove: number[]) => void;
}) {
  const [hall, setHall] = useState(target.hall);
  const [shift, setShift] = useState(target.shift);
  const [dates, setDates] = useState(target.dates);
  const initial = data.assignments.filter(
    (item) =>
      item.hall === target.hall &&
      item.shift === target.shift &&
      target.dates.includes(item.date),
  );
  const [selected, setSelected] = useState<number[]>(
    target.dates.length === 1 ? initial.map((item) => item.supervisor) : [],
  );
  const [replace, setReplace] = useState(target.dates.length === 1);
  const [search, setSearch] = useState("");
  const supervisors = authorizedSupervisors(data.supervisors, hall, search);
  const existing = data.assignments.filter(
    (item) =>
      item.hall === hall && item.shift === shift && dates.includes(item.date),
  );
  const eligible = authorizedSupervisorIds(data, hall);
  function toggle(value: number) {
    setSelected((current) =>
      current.includes(value)
        ? current.filter((id) => id !== value)
        : [...current, value],
    );
  }
  return (
    <Modal
      title={target.dates.length > 1 ? "برنامه‌ریزی گروهی" : "مراقبان این نوبت"}
      description="مراقبان و روزها را انتخاب کنید؛ پیش از ذخیره، همهٔ تغییرات را خواهید دید."
      onClose={onClose}
      wide
    >
      <form
        className="schedule-editor"
        onSubmit={(event) => {
          event.preventDefault();
          const rows = uniqueAssignments(
            dates.flatMap((day) =>
              selected
                .filter((id) => eligible.includes(id))
                .map((supervisor) => ({ date: day, hall, shift, supervisor })),
            ),
          );
          onPreview(
            rows,
            replace
              ? existing
                  .filter((item) => !selected.includes(item.supervisor))
                  .map((item) => item.id)
              : [],
          );
        }}
      >
        <InlineError message={error} />
        <fieldset disabled={pending} className="schedule-editor-fieldset">
          <div className="schedule-form-grid">
            <Field label="سالن">
              <select
                value={hall}
                onChange={(event) => {
                  setHall(Number(event.target.value));
                  setSelected([]);
                }}
                required
              >
                {data.halls.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="شیفت">
              <select
                value={shift}
                onChange={(event) => setShift(Number(event.target.value))}
                required
              >
                {data.shifts
                  .filter((item) => item.is_active)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} · {clockTime(item.start_time)}–
                      {clockTime(item.end_time)}
                    </option>
                  ))}
              </select>
            </Field>
          </div>
          <fieldset className="schedule-days">
            <legend>
              روزهای انتخاب‌شده{" "}
              <button
                type="button"
                className="schedule-text-button"
                onClick={() => setDates(dates.length === 7 ? [] : days)}
              >
                {dates.length === 7 ? "پاک کردن" : "انتخاب هفته"}
              </button>
            </legend>
            <div>
              {days.map((day, index) => (
                <label
                  className={dates.includes(day) ? "selected" : ""}
                  key={day}
                >
                  <input
                    type="checkbox"
                    checked={dates.includes(day)}
                    onChange={() =>
                      setDates((current) =>
                        current.includes(day)
                          ? current.filter((value) => value !== day)
                          : [...current, day],
                      )
                    }
                  />
                  <span>{weekDays[index]}</span>
                  <small>
                    {date(day, {
                      year: undefined,
                      month: "2-digit",
                      day: "2-digit",
                    })}
                  </small>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="schedule-picker-heading">
            <strong>
              مراقبان مجاز این سالن{" "}
              <small>
                {number(selected.filter((id) => eligible.includes(id)).length)}{" "}
                انتخاب
              </small>
            </strong>
            <button
              type="button"
              className="schedule-text-button"
              onClick={() => setSelected(supervisors.map((item) => item.id))}
            >
              انتخاب نتایج
            </button>
          </div>
          <label className="schedule-search">
            <Search size={17} />
            <input
              aria-label="جست‌وجوی مراقب"
              placeholder="نام مراقب…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="schedule-supervisor-picker">
            {supervisors.length ? (
              supervisors.map((item) => (
                <label
                  key={item.id}
                  className={selected.includes(item.id) ? "selected" : ""}
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(item.id)}
                    onChange={() => toggle(item.id)}
                  />
                  <span className="schedule-avatar">
                    {item.first_name.slice(0, 1)}
                  </span>
                  <strong>
                    {item.first_name} {item.last_name}
                  </strong>
                  <Check size={16} />
                </label>
              ))
            ) : (
              <p className="schedule-muted">
                مراقب مجازی پیدا نشد. ابتدا سالن‌های مسئولیت مراقب را تنظیم
                کنید.
              </p>
            )}
          </div>
          <label className="schedule-replace-toggle">
            <input
              type="checkbox"
              checked={replace}
              onChange={(event) => setReplace(event.target.checked)}
            />
            <span>
              جایگزینی فهرست مراقبان در روزهای انتخاب‌شده
              <small>
                {replace
                  ? "مراقبان قبلیِ انتخاب‌نشده برای حذف پیش‌نمایش می‌شوند."
                  : "مراقبان فعلی حفظ می‌شوند و انتخاب‌های جدید افزوده می‌شوند."}
              </small>
            </span>
          </label>
        </fieldset>
        <div className="schedule-dialog-footer">
          <span>
            {number(dates.length)} روز · {number(selected.length)} مراقب
          </span>
          <button
            className="button primary"
            type="submit"
            disabled={
              pending || !dates.length || (!selected.length && !replace)
            }
          >
            <Sparkles size={17} />
            {pending ? "در حال بررسی…" : "پیش‌نمایش تغییرات"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
function authorizedSupervisorIds(data: ScheduleWeek, hall: number) {
  return authorizedSupervisors(data.supervisors, hall).map((item) => item.id);
}

function MonthCopy({
  week,
  pending,
  error,
  onClose,
  onPreview,
}: {
  week: string;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onPreview: (year: number, month: number) => void;
}) {
  const initial = jalaliMonth(week);
  const [year, setYear] = useState(initial.year);
  const [month, setMonth] = useState(initial.month);
  return (
    <Modal title="یک هفته، یک ماه برنامه" onClose={onClose}>
      <form
        className="schedule-editor"
        onSubmit={(event) => {
          event.preventDefault();
          onPreview(year, month);
        }}
      >
        <div className="schedule-copy-banner">
          <Sparkles size={28} />
          <div>
            <strong>الگوی هفتهٔ {date(week)}</strong>
            <p>
              روزهای هفته در تمام ماه تکرار می‌شوند؛ فقط روزهای داخل ماه شمسی
              پیشنهاد می‌شوند.
            </p>
          </div>
        </div>
        <InlineError message={error} />
        <div className="schedule-form-grid">
          <Field label="سال شمسی" required>
            <input
              type="number"
              value={year}
              min={1300}
              max={1600}
              onChange={(event) => setYear(Number(event.target.value))}
              required
              disabled={pending}
            />
          </Field>
          <Field label="ماه شمسی" required>
            <select
              value={month}
              onChange={(event) => setMonth(Number(event.target.value))}
              disabled={pending}
            >
              {monthNames.map((name, index) => (
                <option key={name} value={index + 1}>
                  {name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="schedule-dialog-footer">
          <span>برنامهٔ موجود بدون انتخاب شما تغییر نمی‌کند.</span>
          <button className="button primary" type="submit" disabled={pending}>
            <Sparkles size={17} />
            {pending ? "در حال بررسی…" : "دیدن برنامهٔ پیشنهادی"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function PreviewDialog({
  slug,
  preview,
  data,
  onClose,
  onSaved,
}: {
  slug: string;
  preview: SchedulePreview;
  data: ScheduleWeek;
  onClose: () => void;
  onSaved: (count: number) => void;
}) {
  const [choices, setChoices] = useState(() =>
    initialPreviewChoices(preview.rows),
  );
  const [removals, setRemovals] = useState(() =>
    preview.removals.map((item) => item.id),
  );
  const [confirmed, setConfirmed] = useState(false);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const activeChoices = choices.filter(
    (choice) => choice.action === "add" || choice.action === "replace",
  );
  const conflicts = selectedScheduleConflicts(preview, choices, removals);
  const replacementCount = new Set(
    choices.flatMap((choice) =>
      choice.action === "replace" ? choice.replace_ids || [] : [],
    ),
  ).size;
  const choiceByIndex = new Map(
    choices.map((choice) => [choice.index, choice]),
  );
  const filtered = preview.rows.filter((row) =>
    `${row.supervisor_name} ${row.hall_name} ${row.shift_name} ${date(row.date)}`.includes(
      search.trim(),
    ),
  );
  const pages = Math.max(1, Math.ceil(filtered.length / 30));
  const displayedPage = Math.min(page, pages);
  const rows = filtered.slice((displayedPage - 1) * 30, displayedPage * 30);
  function choose(index: number, action: PreviewAction) {
    setChoices((current) =>
      current.map((choice) =>
        choice.index === index
          ? {
              index,
              action,
              ...(action === "replace" ? { replace_ids: [] } : {}),
            }
          : choice,
      ),
    );
    setConfirmed(false);
  }
  function toggleReplacement(index: number, id: number) {
    setConfirmed(false);
    setChoices((current) =>
      current.map((item) =>
        item.index === index
          ? {
              ...item,
              replace_ids: item.replace_ids?.includes(id)
                ? item.replace_ids.filter((value) => value !== id)
                : [...(item.replace_ids || []), id],
            }
          : item,
      ),
    );
  }
  const deletedIds = new Set([
    ...removals,
    ...choices.flatMap((choice) =>
      choice.action === "replace" ? choice.replace_ids || [] : [],
    ),
  ]);
  const contradictory = preview.rows.some(
    (row) =>
      row.existing_id &&
      deletedIds.has(row.existing_id) &&
      choiceByIndex.get(row.index)?.action === "preserve",
  );
  async function save() {
    setPending(true);
    setError(null);
    try {
      const result = await mutate<{ added: number }>(
        `organizations/${slug}/schedule/apply/`,
        "POST",
        {
          token: preview.token,
          actions: choices,
          remove_ids: removals,
          confirm_conflicts: confirmed,
          override_reason: reason.trim(),
        },
      );
      onSaved(result.added);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setPending(false);
    }
  }
  const incompleteReplacement = choices.some(
    (choice) => choice.action === "replace" && !choice.replace_ids?.length,
  );
  return (
    <Modal
      title="مرور تغییرات برنامه"
      description="تفاوت‌ها را ببینید و برای هر نوبت تصمیم بگیرید."
      onClose={() => !pending && onClose()}
      wide
    >
      <div className="schedule-preview">
        <InlineError message={error} />
        <div className="schedule-preview-summary">
          <span>
            <Plus size={17} />
            <strong>{number(activeChoices.length)}</strong> افزودن
          </span>
          <span>
            <Check size={17} />
            <strong>
              {number(
                choices.filter((choice) => choice.action === "preserve").length,
              )}
            </strong>{" "}
            حفظ
          </span>
          <span>
            <Trash2 size={17} />
            <strong>{number(removals.length + replacementCount)}</strong> حذف
          </span>
          <span className={conflicts.length ? "schedule-warning-text" : ""}>
            <AlertTriangle size={17} />
            <strong>{number(conflicts.length)}</strong> تعارض پیشنهادی
          </span>
        </div>
        <div className="schedule-preview-toolbar">
          <label className="schedule-search">
            <Search size={16} />
            <input
              aria-label="جست‌وجو در پیش‌نمایش"
              placeholder="مراقب، سالن یا روز…"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <button
            className="button subtle compact"
            disabled={pending}
            onClick={() => {
              setChoices(initialPreviewChoices(preview.rows));
              setConfirmed(false);
            }}
          >
            انتخاب‌های امن اولیه
          </button>
          <button
            className="button subtle compact"
            disabled={pending}
            onClick={() => {
              setChoices((current) =>
                current.map((choice) => ({
                  index: choice.index,
                  action: "skip",
                })),
              );
              setRemovals([]);
              setConfirmed(false);
            }}
          >
            رد همه
          </button>
        </div>
        <div className="schedule-preview-scroll">
          <table className="schedule-preview-table">
            <thead>
              <tr>
                <th>روز / سالن</th>
                <th>شیفت / مراقب</th>
                <th>تفاوت</th>
                <th>انتخاب شما</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const choice = choiceByIndex.get(row.index)!;
                const options: PreviewAction[] =
                  row.status === "duplicate" || row.status === "invalid"
                    ? ["skip"]
                    : row.status === "existing"
                      ? ["preserve", "replace", "skip"]
                      : row.existing_ids.length
                        ? ["add", "replace", "skip"]
                        : ["add", "skip"];
                const peers =
                  row.existing_assignments ||
                  data.assignments.filter((item) =>
                    row.existing_ids.includes(item.id),
                  );
                return (
                  <tr
                    key={row.index}
                    className={
                      choice.action === "skip"
                        ? "skipped"
                        : row.conflicts.length
                          ? "conflicting"
                          : ""
                    }
                  >
                    <td>
                      <strong>{date(row.date, { year: undefined })}</strong>
                      <small>{row.hall_name}</small>
                    </td>
                    <td>
                      <strong>{row.supervisor_name}</strong>
                      <small>
                        {row.shift_name} · {clockTime(row.start_time)}–
                        {clockTime(row.end_time)}
                      </small>
                    </td>
                    <td>
                      <span className={`schedule-diff ${row.status}`}>
                        {row.status === "existing"
                          ? "از قبل موجود"
                          : row.status === "duplicate"
                            ? "پیشنهاد تکراری"
                            : row.status === "invalid"
                              ? "غیرقابل ثبت"
                              : "نوبت جدید"}
                      </span>
                      {row.error && <small role="note">{row.error}</small>}
                      {row.times_changed &&
                        row.source_start_time &&
                        row.source_end_time && (
                          <small className="schedule-warning-text">
                            ساعت الگو: {clockTime(row.source_start_time)}–
                            {clockTime(row.source_end_time)} ← ساعت فعلی:{" "}
                            {clockTime(row.start_time)}–
                            {clockTime(row.end_time)}
                          </small>
                        )}
                      {row.conflicts.length > 0 && (
                        <details className="schedule-conflict-details">
                          <summary>
                            <AlertTriangle size={13} />
                            هم‌پوشانی
                          </summary>
                          {row.conflicts.map((conflict, index) => (
                            <p key={index}>
                              {conflict.detail ||
                                `${conflict.supervisor_name || row.supervisor_name} · ${conflict.left_hall || row.hall_name} / ${conflict.right_hall || "سالن دیگر"} · ${clockTime(conflict.start_time)}–${clockTime(conflict.end_time)}`}
                            </p>
                          ))}
                        </details>
                      )}
                    </td>
                    <td>
                      <select
                        aria-label={`تصمیم برای ${row.supervisor_name} در ${date(row.date)} ${row.hall_name} ${row.shift_name}`}
                        value={choice.action}
                        onChange={(event) =>
                          choose(row.index, event.target.value as PreviewAction)
                        }
                        disabled={pending}
                      >
                        {options.map((action) => (
                          <option value={action} key={action}>
                            {actionLabels[action]}
                          </option>
                        ))}
                      </select>
                      {choice.action === "replace" && (
                        <fieldset className="schedule-replacement-choices">
                          <legend>کدام نوبت‌ها حذف شوند؟</legend>
                          {row.existing_ids.map((id) => (
                            <label key={id}>
                              <input
                                type="checkbox"
                                checked={
                                  choice.replace_ids?.includes(id) || false
                                }
                                disabled={
                                  pending ||
                                  preview.rows.some(
                                    (peer) =>
                                      peer.index !== row.index &&
                                      peer.existing_id === id &&
                                      choiceByIndex.get(peer.index)?.action ===
                                        "preserve",
                                  )
                                }
                                onChange={() =>
                                  toggleReplacement(row.index, id)
                                }
                              />
                              {peers.find((peer) => peer.id === id)
                                ?.supervisor_name || `نوبت ${number(id)}`}
                              {preview.rows.some(
                                (peer) =>
                                  peer.index !== row.index &&
                                  peer.existing_id === id &&
                                  choiceByIndex.get(peer.index)?.action ===
                                    "preserve",
                              ) && (
                                <small>
                                  محفوظ؛ ابتدا انتخاب آن را «رد کردن» کنید.
                                </small>
                              )}
                            </label>
                          ))}
                        </fieldset>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!rows.length && (
            <p className="schedule-muted">پیشنهادی برای نمایش نیست.</p>
          )}
        </div>
        {pages > 1 && (
          <div className="schedule-pagination">
            <button
              className="button secondary compact"
              disabled={displayedPage <= 1}
              onClick={() => setPage(displayedPage - 1)}
            >
              قبلی
            </button>
            <span>
              {number(displayedPage)} از {number(pages)}
            </span>
            <button
              className="button secondary compact"
              disabled={displayedPage >= pages}
              onClick={() => setPage(displayedPage + 1)}
            >
              بعدی
            </button>
          </div>
        )}
        {preview.removals.length > 0 && (
          <fieldset className="schedule-removal-list">
            <legend>حذف‌های پیشنهادی؛ برای حفظ نوبت، تیک آن را بردارید</legend>
            {preview.removals.map((item) => (
              <label key={item.id}>
                <input
                  type="checkbox"
                  checked={removals.includes(item.id)}
                  disabled={pending}
                  onChange={() => {
                    setConfirmed(false);
                    setRemovals((current) =>
                      current.includes(item.id)
                        ? current.filter((value) => value !== item.id)
                        : [...current, item.id],
                    );
                  }}
                />
                <Trash2 size={14} />
                <span>
                  {item.supervisor_name} · {item.hall_name} ·{" "}
                  {date(item.date, { year: undefined })} · {item.shift_name}
                </span>
              </label>
            ))}
          </fieldset>
        )}
        {conflicts.length > 0 && (
          <div className="schedule-conflict-confirm">
            <div>
              <AlertTriangle size={20} />
              <strong>این انتخاب‌ها شامل شیفت‌های هم‌زمان است.</strong>
            </div>
            <p>
              با انتخاب حفظ یا رد، تعارض‌های غیرضروری را حذف کنید. تأیید
              هم‌پوشانی همراه با دلیل در سابقه ثبت می‌شود.
            </p>
            <label>
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
                disabled={pending}
              />
              هم‌پوشانی‌های انتخاب‌شده را آگاهانه تأیید می‌کنم.
            </label>
            <Field label="دلیل تأیید هم‌پوشانی">
              <input
                value={reason}
                minLength={3}
                maxLength={240}
                onChange={(event) => setReason(event.target.value)}
                placeholder="مثلاً تحویل شیفت بین دو سالن"
                disabled={pending}
              />
            </Field>
          </div>
        )}
        <div className="schedule-dialog-footer">
          <span>
            {contradictory
              ? "یک نوبت هم برای حفظ و هم حذف انتخاب شده؛ ابتدا انتخاب‌های متناقض را اصلاح کنید."
              : incompleteReplacement
                ? "برای هر جایگزینی، نوبت‌های حذف‌شونده را انتخاب کنید."
                : "برنامهٔ موجود فقط مطابق انتخاب‌های شما تغییر می‌کند."}
          </span>
          <button
            className="button primary"
            disabled={
              pending ||
              contradictory ||
              incompleteReplacement ||
              (!activeChoices.length && !removals.length) ||
              (conflicts.length > 0 && (!confirmed || reason.trim().length < 3))
            }
            onClick={save}
          >
            <CheckCheck size={18} />
            {pending ? "در حال ذخیره…" : "تأیید و ثبت برنامه"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function ShiftManager({
  slug,
  onClose,
  onChanged,
}: {
  slug: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const state = useData<Paginated<WorkShift>>(
    `organizations/${slug}/work-shifts/?status=all&page_size=100`,
  );
  const [edit, setEdit] = useState<WorkShift | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [all, setAll] = useState<WorkShift[] | null>(null);
  const shifts = all || state.data?.results || [];
  async function loadRemaining() {
    if (!state.data?.next) return;
    setPending(true);
    setError(null);
    try {
      const rows = [...state.data.results];
      let page = 2;
      let response: Paginated<WorkShift>;
      do {
        response = await api<Paginated<WorkShift>>(
          `organizations/${slug}/work-shifts/?status=all&page_size=100&page=${page++}`,
        );
        rows.push(...response.results);
      } while (response.next);
      setAll(rows);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function action(item: WorkShift, method: string, body?: unknown) {
    setPending(true);
    setError(null);
    try {
      await mutate(
        `organizations/${slug}/work-shifts/${item.id}/`,
        method,
        body,
      );
      setAll(null);
      state.refresh();
      onChanged();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal
      title="شیفت‌های کاری"
      description="شیفت‌های قابل استفاده در برنامهٔ هفتگی تیم."
      onClose={() => !pending && onClose()}
      wide
    >
      <div className="schedule-shifts">
        <InlineError message={error} />
        {state.error ? (
          <ErrorState error={state.error} retry={state.refresh} />
        ) : state.loading ? (
          <Spinner />
        ) : (
          <>
            <div className="schedule-preview-toolbar">
              <span>{number(state.data?.count || 0)} شیفت</span>
              <button
                className="button primary"
                onClick={() => setEdit("new")}
                disabled={pending}
              >
                <Plus size={17} />
                شیفت جدید
              </button>
            </div>
            {shifts.length ? (
              <div className="schedule-shift-list">
                {shifts.map((item) => (
                  <article key={item.id}>
                    <span
                      className={`schedule-shift-icon ${item.is_active ? "" : "inactive"}`}
                    >
                      <Clock3 size={22} />
                    </span>
                    <div>
                      <strong>{item.name}</strong>
                      <small>
                        {clockTime(item.start_time)} تا{" "}
                        {clockTime(item.end_time)}
                      </small>
                    </div>
                    <span
                      className={`schedule-diff ${item.is_active ? "new" : "duplicate"}`}
                    >
                      {item.is_active ? "فعال" : "غیرفعال"}
                    </span>
                    <button
                      className="icon-button"
                      aria-label={`ویرایش شیفت ${item.name}`}
                      onClick={() => setEdit(item)}
                      disabled={pending}
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      className="button subtle compact"
                      onClick={() =>
                        action(item, "PATCH", { is_active: !item.is_active })
                      }
                      disabled={pending}
                    >
                      {item.is_active ? "غیرفعال" : "فعال‌سازی"}
                    </button>
                    <button
                      className="icon-button"
                      aria-label={`بایگانی شیفت ${item.name}`}
                      disabled={pending}
                      onClick={() => {
                        if (
                          window.confirm(
                            `شیفت «${item.name}» بایگانی شود؟ برنامه‌های ثبت‌شده حفظ می‌شوند.`,
                          )
                        )
                          action(item, "DELETE");
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <Empty
                title="هنوز شیفتی ندارید"
                description="نام و ساعت یک شیفت کاری را ثبت کنید."
              />
            )}
            {state.data?.next && !all && (
              <button
                className="button secondary"
                disabled={pending}
                onClick={loadRemaining}
              >
                نمایش همهٔ شیفت‌ها
              </button>
            )}
          </>
        )}
        {edit && (
          <ShiftForm
            key={edit === "new" ? "new" : edit.id}
            slug={slug}
            shift={edit === "new" ? undefined : edit}
            onClose={() => setEdit(null)}
            onSaved={() => {
              setEdit(null);
              setAll(null);
              state.refresh();
              onChanged();
            }}
          />
        )}
      </div>
    </Modal>
  );
}

function ShiftForm({
  slug,
  shift,
  onClose,
  onSaved,
}: {
  slug: string;
  shift?: WorkShift;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal
      title={shift ? "ویرایش شیفت" : "شیفت کاری جدید"}
      onClose={() => !pending && onClose()}
    >
      <form
        className="schedule-editor"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const name = String(form.get("name") || "").trim();
          const start_time = String(form.get("start_time") || "");
          const end_time = String(form.get("end_time") || "");
          const validation = validateShift(name, start_time, end_time);
          if (validation) {
            setError(validation);
            return;
          }
          setPending(true);
          setError(null);
          try {
            await mutate(
              `organizations/${slug}/work-shifts/${shift ? `${shift.id}/` : ""}`,
              shift ? "PATCH" : "POST",
              {
                name,
                start_time,
                end_time,
                is_active: form.get("is_active") === "on",
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
        <fieldset disabled={pending} className="schedule-editor-fieldset">
          <Field label="نام شیفت" required>
            <input
              name="name"
              required
              maxLength={100}
              placeholder="مثلاً شیفت صبح"
              defaultValue={shift?.name}
            />
          </Field>
          <div className="schedule-form-grid">
            <Field label="ساعت شروع" required>
              <input
                name="start_time"
                type="time"
                dir="ltr"
                required
                defaultValue={shift?.start_time.slice(0, 5)}
              />
            </Field>
            <Field label="ساعت پایان" required>
              <input
                name="end_time"
                type="time"
                dir="ltr"
                required
                defaultValue={shift?.end_time.slice(0, 5)}
              />
            </Field>
          </div>
          <label className="schedule-checkbox">
            <input
              type="checkbox"
              name="is_active"
              defaultChecked={shift?.is_active ?? true}
            />
            شیفت فعال است
          </label>
        </fieldset>
        <div className="schedule-dialog-footer">
          <span>زمان پایان باید بعد از شروع همان روز باشد.</span>
          <button className="button primary" disabled={pending} type="submit">
            <Check size={17} />
            {pending ? "در حال ذخیره…" : "ذخیره شیفت"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
