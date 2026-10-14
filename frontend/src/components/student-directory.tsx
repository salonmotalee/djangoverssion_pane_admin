"use client";
import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Archive,
  ArrowRight,
  ArrowUpLeft,
  GraduationCap,
  Pencil,
  Plus,
  RotateCcw,
  Search,
} from "lucide-react";
import { mutate } from "@/lib/api";
import { date, number, queryString } from "@/lib/format";
import {
  grades,
  majors,
  type Hall,
  type Student,
  type OperationsSummary,
} from "@/lib/operations";
import type { Paginated } from "@/lib/types";
import { useData } from "@/lib/use-data";
import {
  Empty,
  ErrorState,
  Field,
  InlineError,
  Modal,
  PageHeading,
  Pagination,
  Spinner,
} from "./ui";
import { StudentForm } from "./operations-forms";
import { ActiveStatus, ArchiveDialog } from "./operations-common";
import { HelpTooltip } from "./help-tooltip";

export function StudentDirectory({
  slug,
  onChanged,
  summary,
}: {
  slug: string;
  onChanged: () => void;
  summary?: OperationsSummary;
}) {
  const params = useSearchParams(),
    base = `organizations/${slug}/students/`;
  const [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [hall, setHall] = useState(params.get("hall") || "");
  const [grade, setGrade] = useState(""),
    [major, setMajor] = useState(""),
    [status, setStatus] = useState("active"),
    [ordering, setOrdering] = useState("-created_at");
  const [edit, setEdit] = useState<Student | "new" | null>(null),
    [archive, setArchive] = useState<Student | null>(null),
    [selected, setSelected] = useState<number[]>([]);
  const [bulkAction, setBulkAction] = useState<
      "archive" | "restore" | "transfer" | null
    >(null),
    [targetHall, setTargetHall] = useState("");
  const [notice, setNotice] = useState(""),
    [error, setError] = useState<string | null>(null),
    [pending, setPending] = useState(false);
  const data = useData<Paginated<Student>>(
    base +
      "?" +
      queryString({ page, search, hall, grade, major, status, ordering }),
  );
  const options = useData<Hall[]>(`organizations/${slug}/halls/options/`);
  function filter(action: () => void) {
    action();
    setPage(1);
    setSelected([]);
  }
  function saved() {
    setPage(1);
    setEdit(null);
    setArchive(null);
    setBulkAction(null);
    setSelected([]);
    setNotice("تغییرات دانش‌آموزان با موفقیت ذخیره شد.");
    setError(null);
    data.refresh();
    onChanged();
  }
  const rows = data.data?.results || [];
  return (
    <div className="ops-page">
      <PageHeading title="دانش‌آموزان">
        <HelpTooltip
          label="راهنمای مدیریت دانش‌آموزان"
          content="دانش‌آموزان را ثبت، ویرایش یا بین سالن‌ها منتقل کنید. دانش‌آموزان فعال از ظرفیت مشترک مجموعه استفاده می‌کنند؛ بایگانی‌شده‌ها ظرفیت اشغال نمی‌کنند."
        />
        <button
          className="button primary"
          disabled={options.loading || !!options.error}
          onClick={() => setEdit("new")}
        >
          <Plus size={18} /> ثبت دانش‌آموز
        </button>
      </PageHeading>
      {summary && (
        <div className="ops-enrollment-summary">
          <span>
            فعال‌ها <strong>{number(summary.active_students)}</strong>
          </span>
          <span>
            ظرفیت کل{" "}
            <strong>
              {summary.capacity === null ? "—" : number(summary.capacity)}
            </strong>
          </span>
          <span>
            ظرفیت باقی‌مانده{" "}
            <strong>
              {summary.remaining_capacity === null
                ? "—"
                : number(summary.remaining_capacity)}
            </strong>
          </span>
          {summary.over_capacity && (
            <strong className="ops-capacity-alert" role="status">
              تعداد ثبت‌نام از ظرفیت فعلی بیشتر است.
            </strong>
          )}
        </div>
      )}
      {notice && (
        <div className="ops-success" role="status">
          {notice}
        </div>
      )}
      <InlineError message={error || options.error} />
      <div className="ops-toolbar ops-student-search">
        <label className="ops-search">
          <Search size={18} />
          <input
            aria-label="جست‌وجوی دانش‌آموز"
            placeholder="شناسه، نام، تلفن یا شماره میز…"
            value={search}
            onChange={(event) => filter(() => setSearch(event.target.value))}
          />
        </label>
        <select
          aria-label="وضعیت دانش‌آموزان"
          value={status}
          onChange={(event) => filter(() => setStatus(event.target.value))}
        >
          <option value="active">دانش‌آموزان فعال</option>
          <option value="archived">بایگانی‌شده‌ها</option>
          <option value="all">همهٔ دانش‌آموزان</option>
        </select>
        <span className="ops-result-count">
          {number(data.data?.count || 0)} نتیجه
        </span>
      </div>
      <div className="ops-filters">
        <label>
          سالن
          <select
            aria-label="فیلتر سالن"
            value={hall}
            onChange={(event) => filter(() => setHall(event.target.value))}
          >
            <option value="">همهٔ سالن‌ها</option>
            {options.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
            {hall &&
              !options.data?.some((item) => item.id === Number(hall)) && (
                <option value={hall}>سالن بایگانی‌شده</option>
              )}
          </select>
        </label>
        <label>
          پایه
          <select
            aria-label="فیلتر پایه"
            value={grade}
            onChange={(event) => filter(() => setGrade(event.target.value))}
          >
            <option value="">همهٔ پایه‌ها</option>
            {Object.entries(grades).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          رشته
          <select
            aria-label="فیلتر رشته"
            value={major}
            onChange={(event) => filter(() => setMajor(event.target.value))}
          >
            <option value="">همهٔ رشته‌ها</option>
            {Object.entries(majors).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          مرتب‌سازی
          <select
            aria-label="مرتب‌سازی دانش‌آموزان"
            value={ordering}
            onChange={(event) => filter(() => setOrdering(event.target.value))}
          >
            <option value="-created_at">جدیدترین ثبت‌نام</option>
            <option value="created_at">قدیمی‌ترین ثبت‌نام</option>
            <option value="last_name">نام خانوادگی</option>
            <option value="identifier">شناسه دانش‌آموز</option>
            <option value="desk_number">شماره میز</option>
            <option value="grade">پایهٔ تحصیلی</option>
          </select>
        </label>
        <button
          className="button secondary"
          onClick={() =>
            filter(() => {
              setSearch("");
              setHall("");
              setGrade("");
              setMajor("");
              setStatus("active");
              setOrdering("-created_at");
            })
          }
        >
          پاک‌کردن فیلترها
        </button>
      </div>
      {!!selected.length && (
        <div className="ops-bulk-bar">
          <strong>{number(selected.length)} دانش‌آموز انتخاب شده</strong>
          <div className="heading-actions">
            <button
              className="button secondary"
              onClick={() => setBulkAction("transfer")}
            >
              انتقال به سالن
            </button>
            <button
              className="button secondary"
              onClick={() => setBulkAction("archive")}
            >
              بایگانی گروهی
            </button>
            <button
              className="button secondary"
              onClick={() => setBulkAction("restore")}
            >
              بازیابی گروهی
            </button>
            <button
              className="icon-button"
              aria-label="لغو انتخاب دانش‌آموزان"
              onClick={() => setSelected([])}
            >
              ×
            </button>
          </div>
        </div>
      )}
      {data.error ? (
        <ErrorState error={data.error} retry={data.refresh} />
      ) : data.loading ? (
        <Spinner />
      ) : !rows.length ? (
        <Empty
          title={
            search || hall || grade || major || status !== "active"
              ? "دانش‌آموزی با این شرایط پیدا نشد"
              : "اولین همراه این مسیر را ثبت کنید"
          }
          description="برای ثبت دانش‌آموز، یک سالن فعال و ظرفیت خالی در مجموعه لازم است."
          action={
            <button
              className="button primary"
              disabled={options.loading || !!options.error}
              onClick={() => setEdit("new")}
            >
              ثبت دانش‌آموز
            </button>
          }
        />
      ) : (
        <div className="ops-table-card">
          <div className="ops-table-scroll">
            <table
              className="ops-table ops-students-table"
              data-testid="students-table"
            >
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      aria-label="انتخاب همهٔ دانش‌آموزان این صفحه"
                      checked={
                        rows.length > 0 &&
                        rows.every((row) => selected.includes(row.id))
                      }
                      onChange={() =>
                        setSelected(
                          rows.every((row) => selected.includes(row.id))
                            ? []
                            : rows.map((row) => row.id),
                        )
                      }
                    />
                  </th>
                  <th>دانش‌آموز / شناسه</th>
                  <th>سالن و میز</th>
                  <th>اطلاعات تحصیلی</th>
                  <th>شماره همراه</th>
                  <th>وضعیت</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    className={selected.includes(row.id) ? "selected" : ""}
                  >
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`انتخاب ${row.identifier}`}
                        checked={selected.includes(row.id)}
                        onChange={() =>
                          setSelected(
                            selected.includes(row.id)
                              ? selected.filter((id) => id !== row.id)
                              : [...selected, row.id],
                          )
                        }
                      />
                    </td>
                    <td>
                      <Link
                        className="ops-student-name"
                        href={`/${slug}/students/${row.id}`}
                      >
                        <span className="ops-avatar">
                          {row.first_name.slice(0, 1)}
                        </span>
                        <span>
                          <strong>
                            {row.first_name} {row.last_name}
                          </strong>
                          <small>{row.identifier}</small>
                        </span>
                      </Link>
                    </td>
                    <td>
                      <strong>{row.hall_name}</strong>
                      <small className="ops-cell-subtitle">
                        میز {row.desk_number || "—"}
                      </small>
                    </td>
                    <td>
                      {grades[row.grade]}
                      <small className="ops-cell-subtitle">
                        {majors[row.major]}
                      </small>
                    </td>
                    <td dir="ltr">{row.primary_phone}</td>
                    <td>
                      <ActiveStatus active={row.is_active} />
                    </td>
                    <td>
                      <div className="ops-actions">
                        <Link
                          className="icon-button"
                          href={`/${slug}/students/${row.id}`}
                          aria-label={`جزئیات ${row.identifier}`}
                        >
                          <ArrowUpLeft size={16} />
                        </Link>
                        <button
                          className="icon-button"
                          aria-label={`ویرایش ${row.identifier}`}
                          onClick={() => setEdit(row)}
                        >
                          <Pencil size={16} />
                        </button>
                        {row.is_active ? (
                          <button
                            className="icon-button"
                            aria-label={`بایگانی ${row.identifier}`}
                            onClick={() => setArchive(row)}
                          >
                            <Archive size={16} />
                          </button>
                        ) : (
                          <button
                            className="icon-button"
                            disabled={pending}
                            aria-label={`بازیابی ${row.identifier}`}
                            onClick={async () => {
                              setPending(true);
                              try {
                                await mutate(
                                  base + `${row.id}/restore/`,
                                  "POST",
                                );
                                saved();
                              } catch (error) {
                                setError((error as Error).message);
                              } finally {
                                setPending(false);
                              }
                            }}
                          >
                            <RotateCcw size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            count={data.data?.count || 0}
            page={page}
            onPage={(next) => {
              setPage(next);
              setSelected([]);
            }}
          />
        </div>
      )}
      {edit && (
        <StudentForm
          slug={slug}
          student={edit === "new" ? undefined : edit}
          halls={options.data || []}
          onClose={() => setEdit(null)}
          onSaved={saved}
        />
      )}
      {archive && (
        <ArchiveDialog
          title="بایگانی دانش‌آموز"
          description={`${archive.first_name} ${archive.last_name} از فهرست فعال خارج می‌شود و یک ظرفیت آزاد خواهد شد. شناسهٔ او محفوظ می‌ماند.`}
          endpoint={base + `${archive.id}/`}
          onClose={() => setArchive(null)}
          onSaved={saved}
        />
      )}
      {bulkAction && (
        <Modal
          title={
            bulkAction === "transfer"
              ? "انتقال گروهی دانش‌آموزان"
              : bulkAction === "archive"
                ? "بایگانی گروهی دانش‌آموزان"
                : "بازیابی گروهی دانش‌آموزان"
          }
          onClose={() => {
            if (!pending) setBulkAction(null);
          }}
        >
          <p>
            {number(selected.length)} دانش‌آموز انتخاب شده است. عملیات به‌صورت
            یکپارچه انجام می‌شود؛ در صورت نامعتبر بودن حتی یک مورد، هیچ تغییری
            ثبت نمی‌شود.
          </p>
          {bulkAction === "transfer" && (
            <Field label="سالن مقصد" required>
              <select
                value={targetHall}
                onChange={(event) => setTargetHall(event.target.value)}
              >
                <option value="">انتخاب سالن</option>
                {options.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <InlineError message={error} />
          <div className="modal-footer">
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => setBulkAction(null)}
            >
              انصراف
            </button>
            <button
              className="button primary"
              disabled={pending || (bulkAction === "transfer" && !targetHall)}
              onClick={async () => {
                setPending(true);
                setError(null);
                try {
                  await mutate(base + "bulk/", "POST", {
                    ids: selected,
                    action: bulkAction,
                    ...(bulkAction === "transfer"
                      ? { hall: Number(targetHall) }
                      : {}),
                  });
                  saved();
                } catch (error) {
                  setError((error as Error).message);
                } finally {
                  setPending(false);
                }
              }}
            >
              {pending ? "در حال انجام…" : "تأیید عملیات گروهی"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export function StudentDetails({
  slug,
  id,
  onChanged,
}: {
  slug: string;
  id: number;
  onChanged: () => void;
}) {
  const base = `organizations/${slug}/students/${id}/`,
    data = useData<Student>(base),
    options = useData<Hall[]>(`organizations/${slug}/halls/options/`);
  const [edit, setEdit] = useState(false),
    [archive, setArchive] = useState(false),
    [pending, setPending] = useState(false),
    [error, setError] = useState<string | null>(null),
    [notice, setNotice] = useState("");
  function saved() {
    setEdit(false);
    setArchive(false);
    setError(null);
    setNotice("اطلاعات دانش‌آموز به‌روز شد.");
    data.refresh();
    onChanged();
  }
  if (data.error) return <ErrorState error={data.error} retry={data.refresh} />;
  if (data.loading || !data.data) return <Spinner />;
  const student = data.data;
  const details = [
    ["شناسه دانش‌آموز", student.identifier],
    ["نام", student.first_name],
    ["نام خانوادگی", student.last_name],
    ["شماره میز", student.desk_number || "—"],
    ["سالن", student.hall_name],
    ["پایه تحصیلی", grades[student.grade]],
    ["رشته تحصیلی", majors[student.major]],
    ["شماره همراه اصلی", student.primary_phone],
    ["شماره همراه دوم", student.secondary_phone || "—"],
    ["تاریخ ثبت", date(student.created_at)],
    ["آخرین ویرایش", date(student.updated_at)],
  ];
  return (
    <div className="ops-page">
      <Link className="ops-back" href={`/${slug}/students`}>
        <ArrowRight size={17} /> بازگشت به دانش‌آموزان
      </Link>
      <PageHeading
        eyebrow="پروندهٔ دانش‌آموز"
        title={`${student.first_name} ${student.last_name}`}
        description={`شناسه ${student.identifier}`}
      >
        <HelpTooltip
          label="راهنمای پروندهٔ دانش‌آموز"
          content="این پرونده اطلاعات ثبت‌نام دانش‌آموز است و حساب ورود ندارد. ویرایش اطلاعات و جابه‌جایی سالن از همین صفحه انجام می‌شود."
        />
        <button
          className="button secondary"
          disabled={!options.data}
          onClick={() => setEdit(true)}
        >
          <Pencil size={16} /> ویرایش دانش‌آموز
        </button>
        {student.is_active ? (
          <button className="button secondary" onClick={() => setArchive(true)}>
            <Archive size={16} /> بایگانی دانش‌آموز
          </button>
        ) : (
          <button
            className="button primary"
            disabled={pending}
            onClick={async () => {
              setPending(true);
              try {
                await mutate(base + "restore/", "POST");
                saved();
              } catch (error) {
                setError((error as Error).message);
              } finally {
                setPending(false);
              }
            }}
          >
            <RotateCcw size={16} /> بازیابی دانش‌آموز
          </button>
        )}
      </PageHeading>
      {notice && (
        <div className="ops-success" role="status">
          {notice}
        </div>
      )}
      <InlineError message={error || options.error} />
      <section className="tenant-card ops-student-profile">
        <div className="ops-profile-heading">
          <span className="ops-profile-avatar">
            <GraduationCap size={38} />
          </span>
          <div>
            <h2>
              {student.first_name} {student.last_name}
            </h2>
            <p>
              {student.hall_name} · {grades[student.grade]} ·{" "}
              {majors[student.major]}
            </p>
          </div>
          <ActiveStatus active={student.is_active} />
        </div>
        <dl>
          {details.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      {edit && (
        <StudentForm
          slug={slug}
          student={student}
          halls={options.data || []}
          onClose={() => setEdit(false)}
          onSaved={saved}
        />
      )}
      {archive && (
        <ArchiveDialog
          title="بایگانی دانش‌آموز"
          description="اطلاعات و شناسه حفظ می‌شود و دانش‌آموز از ظرفیت فعال خارج خواهد شد."
          endpoint={base}
          onClose={() => setArchive(false)}
          onSaved={saved}
        />
      )}
    </div>
  );
}
