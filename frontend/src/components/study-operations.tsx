"use client";
import { useState } from "react";
import Link from "next/link";
import {
  Archive,
  Building2,
  Clock3,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  Grid2x2,
} from "lucide-react";
import { mutate } from "@/lib/api";
import { number, queryString } from "@/lib/format";
import {
  clockTime,
  compareSessions,
  type Hall,
  type StudySession,
  type OperationPage,
  type OperationsSummary,
} from "@/lib/operations";
import type { Paginated } from "@/lib/types";
import { useData } from "@/lib/use-data";
import {
  Empty,
  ErrorState,
  InlineError,
  PageHeading,
  Pagination,
  Spinner,
} from "./ui";
import { HallForm, StudySessionForm } from "./operations-forms";
import { AssignmentMatrix } from "./assignment-matrix";
import { ActiveStatus, ArchiveDialog } from "./operations-common";
import { StudentDirectory, StudentDetails } from "./student-directory";
import { HelpTooltip } from "./help-tooltip";

export function OperationsContent({
  slug,
  page,
  studentId,
  onChanged,
  summary,
}: {
  slug: string;
  page: OperationPage;
  studentId?: number;
  onChanged: () => void;
  summary?: OperationsSummary;
}) {
  if (page === "assignments")
    return <AssignmentMatrix slug={slug} onChanged={onChanged} />;
  if (page === "students")
    return studentId ? (
      <StudentDetails slug={slug} id={studentId} onChanged={onChanged} />
    ) : (
      <StudentDirectory slug={slug} onChanged={onChanged} summary={summary} />
    );
  return (
    <EntityDirectory key={page} slug={slug} kind={page} onChanged={onChanged} />
  );
}

function EntityDirectory({
  slug,
  kind,
  onChanged,
}: {
  slug: string;
  kind: "halls" | "study-sessions";
  onChanged: () => void;
}) {
  const halls = kind === "halls",
    base = `organizations/${slug}/${kind}/`;
  const [page, setPage] = useState(1),
    [status, setStatus] = useState("active"),
    [search, setSearch] = useState("");
  const [edit, setEdit] = useState<Hall | StudySession | "new" | null>(null),
    [archive, setArchive] = useState<Hall | StudySession | null>(null);
  const [notice, setNotice] = useState(""),
    [error, setError] = useState<string | null>(null),
    [pending, setPending] = useState(false);
  const data = useData<Paginated<Hall | StudySession>>(
    base + "?" + queryString({ page, status, search }),
  );
  function saved() {
    setPage(1);
    setEdit(null);
    setArchive(null);
    setNotice("تغییرات با موفقیت ذخیره شد.");
    setError(null);
    data.refresh();
    onChanged();
  }
  const rows = halls
    ? data.data?.results
    : (data.data?.results as StudySession[] | undefined)?.toSorted(
        compareSessions,
      );
  return (
    <div className="ops-page">
      <PageHeading title={halls ? "سالن‌ها" : "پارت‌های مطالعاتی"}>
        <HelpTooltip
          label={halls ? "راهنمای مدیریت سالن‌ها" : "راهنمای پارت‌های مطالعاتی"}
          content={
            halls
              ? "پس از ساخت سالن، دانش‌آموزان و پارت‌ها را به آن اختصاص دهید. ظرفیت ثبت‌نام بین همهٔ سالن‌ها مشترک است."
              : "پارت‌ها بر اساس ساعت شروع مرتب می‌شوند. ساعت پایان باید بعد از شروع همان روز باشد؛ پارت شبانه پشتیبانی نمی‌شود."
          }
        />
        <button className="button primary" onClick={() => setEdit("new")}>
          <Plus size={18} />
          {halls ? "سالن جدید" : "پارت جدید"}
        </button>
      </PageHeading>
      <div className="ops-directory-context">
        <Link
          href={`/${slug}/assignments`}
          className="button secondary compact"
        >
          <Grid2x2 size={16} /> تخصیص پارت‌ها
        </Link>
      </div>
      {notice && (
        <div className="ops-success" role="status">
          {notice}
        </div>
      )}
      <InlineError message={error} />
      <div className="ops-toolbar">
        <label className="ops-search">
          <Search size={17} />
          <input
            aria-label={halls ? "جست‌وجوی سالن" : "جست‌وجوی پارت"}
            placeholder="جست‌وجو…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <select
          aria-label="وضعیت نمایش"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="active">فعال‌ها</option>
          <option value="archived">بایگانی‌شده‌ها</option>
          <option value="all">همه</option>
        </select>
        <span className="ops-result-count">
          {number(data.data?.count || 0)} مورد
        </span>
      </div>
      {data.error ? (
        <ErrorState error={data.error} retry={data.refresh} />
      ) : data.loading ? (
        <Spinner />
      ) : !rows?.length ? (
        <Empty
          title={
            search || status === "archived"
              ? "موردی پیدا نشد"
              : halls
                ? "اولین سالن را بسازید"
                : "روزتان را برنامه‌ریزی کنید"
          }
          description={
            halls
              ? "پس از ساخت سالن، پارت‌ها و دانش‌آموزان را به آن اختصاص دهید."
              : "پارت‌ها پس از ثبت، همیشه از زودترین ساعت شروع نمایش داده می‌شوند."
          }
          action={
            <button className="button primary" onClick={() => setEdit("new")}>
              {" "}
              {halls ? "ساخت سالن" : "ساخت پارت"}
            </button>
          }
        />
      ) : (
        <div className="ops-table-card">
          <div className="ops-table-scroll">
            <table
              className="ops-table"
              data-testid={halls ? "halls-table" : "sessions-table"}
            >
              <thead>
                <tr>
                  <th>{halls ? "نام سالن" : "پارت مطالعاتی"}</th>
                  {halls ? (
                    <>
                      <th>توضیحات</th>
                      <th>دانش‌آموز فعال</th>
                    </>
                  ) : (
                    <>
                      <th>شروع</th>
                      <th>پایان</th>
                    </>
                  )}
                  <th>وضعیت</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <div className="ops-entity-name">
                        <span
                          className={`ops-mini-icon ${halls ? "blue" : "orange"}`}
                        >
                          {halls ? (
                            <Building2 size={17} />
                          ) : (
                            <Clock3 size={17} />
                          )}
                        </span>
                        <strong>
                          {halls
                            ? (row as Hall).name
                            : (row as StudySession).title || "پارت مطالعاتی"}
                        </strong>
                      </div>
                    </td>
                    {halls ? (
                      <>
                        <td className="ops-description">
                          {(row as Hall).description || "—"}
                        </td>
                        <td>
                          <Link
                            href={`/${slug}/students?hall=${row.id}`}
                            className="ops-number-link"
                          >
                            {number((row as Hall).active_students)}
                          </Link>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="ops-clock" dir="ltr">
                          {clockTime((row as StudySession).start_time)}
                        </td>
                        <td className="ops-clock" dir="ltr">
                          {clockTime((row as StudySession).end_time)}
                        </td>
                      </>
                    )}
                    <td>
                      <ActiveStatus active={row.is_active} />
                    </td>
                    <td>
                      <div className="ops-actions">
                        <button
                          className="icon-button"
                          aria-label={
                            halls
                              ? `ویرایش ${(row as Hall).name}`
                              : `ویرایش پارت ${clockTime((row as StudySession).start_time)}`
                          }
                          onClick={() => setEdit(row)}
                        >
                          <Pencil size={16} />
                        </button>
                        {row.is_active ? (
                          <button
                            className="icon-button"
                            aria-label="بایگانی"
                            onClick={() => setArchive(row)}
                          >
                            <Archive size={16} />
                          </button>
                        ) : (
                          <button
                            className="icon-button"
                            disabled={pending}
                            aria-label="بازیابی"
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
            onPage={setPage}
          />
        </div>
      )}
      {edit &&
        (halls ? (
          <HallForm
            slug={slug}
            hall={edit === "new" ? undefined : (edit as Hall)}
            onClose={() => setEdit(null)}
            onSaved={saved}
          />
        ) : (
          <StudySessionForm
            slug={slug}
            session={edit === "new" ? undefined : (edit as StudySession)}
            onClose={() => setEdit(null)}
            onSaved={saved}
          />
        ))}
      {archive && (
        <ArchiveDialog
          title={halls ? "بایگانی سالن" : "بایگانی پارت"}
          description={
            halls
              ? "ابتدا دانش‌آموزان فعال سالن را منتقل یا بایگانی کنید. تخصیص پارت‌های این سالن پاک می‌شود."
              : "با بایگانی پارت، تخصیص‌های آن از همهٔ سالن‌ها برداشته می‌شود."
          }
          endpoint={base + `${archive.id}/`}
          onClose={() => setArchive(null)}
          onSaved={saved}
        />
      )}
    </div>
  );
}
