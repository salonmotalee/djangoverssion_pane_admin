"use client";
import Link from "next/link";
import { useState } from "react";
import { Check, Grid2x2, RotateCcw, Save, Search } from "lucide-react";
import { mutate } from "@/lib/api";
import { number } from "@/lib/format";
import {
  compareSessions,
  clockTime,
  type AssignmentData,
} from "@/lib/operations";
import { useData } from "@/lib/use-data";
import { Empty, ErrorState, InlineError, PageHeading, Spinner } from "./ui";

export function AssignmentMatrix({
  slug,
  onChanged,
}: {
  slug: string;
  onChanged: () => void;
}) {
  const [saved, setSaved] = useState(false);
  const { data, error, loading, refresh } = useData<AssignmentData>(
    `organizations/${slug}/assignments/`,
  );
  if (error) return <ErrorState error={error} retry={refresh} />;
  if (loading || !data) return <Spinner />;
  return (
    <>
      <div role="status" className={saved ? "ops-success" : "sr-only"}>
        {saved ? "تخصیص‌ها ذخیره شدند." : ""}
      </div>
      <MatrixEditor
        slug={slug}
        data={data}
        onChanged={() => {
          setSaved(true);
          refresh();
          onChanged();
        }}
      />
    </>
  );
}

function MatrixEditor({
  slug,
  data,
  onChanged,
}: {
  slug: string;
  data: AssignmentData;
  onChanged: () => void;
}) {
  const initial = data.assignments.map(
    (pair) => `${pair.hall}:${pair.session}`,
  );
  const [selected, setSelected] = useState(new Set(initial)),
    [search, setSearch] = useState("");
  const [pending, setPending] = useState(false),
    [error, setError] = useState<string | null>(null),
    [saved, setSaved] = useState(false);
  const sessions = data.sessions.toSorted(compareSessions),
    halls = data.halls.filter((hall) => hall.name.includes(search));
  const dirty =
    initial.length !== selected.size ||
    initial.some((pair) => !selected.has(pair));
  function toggle(keys: string[]) {
    const next = new Set(selected),
      checked = keys.every((key) => next.has(key));
    keys.forEach((key) => (checked ? next.delete(key) : next.add(key)));
    setSelected(next);
    setSaved(false);
  }
  return (
    <div className="ops-page">
      <PageHeading
        eyebrow="یک برنامه، چند سالن"
        title="تخصیص پارت‌ها"
        description="سطر، ستون یا هر خانه را انتخاب کنید؛ تغییرات با یک ذخیره ثبت می‌شوند."
      />
      <InlineError message={error} />
      {saved && (
        <div className="ops-success" role="status">
          <Check size={18} /> تخصیص‌ها ذخیره شدند.
        </div>
      )}
      {!data.halls.length || !sessions.length ? (
        <Empty
          title="برای برنامه‌ریزی آماده شوید"
          description="ابتدا حداقل یک سالن و یک پارت فعال بسازید."
          action={
            <div className="heading-actions">
              <Link className="button primary" href={`/${slug}/halls`}>
                ساخت سالن
              </Link>
              <Link
                className="button secondary"
                href={`/${slug}/study-sessions`}
              >
                ساخت پارت
              </Link>
            </div>
          }
        />
      ) : (
        <>
          <div className="ops-matrix-intro">
            <span className="tenant-card-icon purple">
              <Grid2x2 size={25} />
            </span>
            <div>
              <strong>برنامهٔ مطالعاتی مجموعه</strong>
              <p>
                {number(data.halls.length)} سالن · {number(sessions.length)}{" "}
                پارت · {number(selected.size)} تخصیص
              </p>
            </div>
            <span className={`ops-status ${dirty ? "draft" : "active"}`}>
              {dirty ? "تغییرات ذخیره نشده" : "برنامهٔ ذخیره‌شده"}
            </span>
          </div>
          <div className="ops-toolbar">
            <label className="ops-search">
              <Search size={17} />
              <input
                aria-label="جست‌وجوی سالن در ماتریس"
                placeholder="جست‌وجوی سالن…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => {
                setSelected(
                  new Set(
                    data.halls.flatMap((hall) =>
                      sessions.map((session) => `${hall.id}:${session.id}`),
                    ),
                  ),
                );
                setSaved(false);
              }}
            >
              انتخاب همه
            </button>
            <button
              className="button secondary"
              disabled={pending}
              onClick={() => {
                setSelected(new Set());
                setSaved(false);
              }}
            >
              پاک کردن همه
            </button>
          </div>
          <div className="ops-table-scroll ops-matrix-scroll">
            <table className="ops-table ops-matrix">
              <caption className="sr-only">
                ماتریس تخصیص پارت‌های مرتب‌شده بر اساس ساعت شروع به سالن‌ها
              </caption>
              <thead>
                <tr>
                  <th>
                    سالن / پارت <small>به ترتیب ساعت شروع</small>
                  </th>
                  {sessions.map((session) => (
                    <th key={session.id}>
                      <label>
                        <input
                          type="checkbox"
                          disabled={pending}
                          aria-label={`انتخاب ستون ${session.title || clockTime(session.start_time)}`}
                          checked={data.halls.every((hall) =>
                            selected.has(`${hall.id}:${session.id}`),
                          )}
                          onChange={() =>
                            toggle(
                              data.halls.map(
                                (hall) => `${hall.id}:${session.id}`,
                              ),
                            )
                          }
                        />
                        <span>
                          {session.title || "پارت مطالعاتی"}
                          <small dir="ltr">
                            {clockTime(session.start_time)} –{" "}
                            {clockTime(session.end_time)}
                          </small>
                        </span>
                      </label>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {halls.map((hall) => (
                  <tr key={hall.id}>
                    <th scope="row">
                      <label>
                        <input
                          type="checkbox"
                          disabled={pending}
                          aria-label={`انتخاب سطر ${hall.name}`}
                          checked={sessions.every((session) =>
                            selected.has(`${hall.id}:${session.id}`),
                          )}
                          onChange={() =>
                            toggle(
                              sessions.map(
                                (session) => `${hall.id}:${session.id}`,
                              ),
                            )
                          }
                        />
                        <span>
                          {hall.name}
                          <small>
                            {number(hall.active_students)} دانش‌آموز فعال
                          </small>
                        </span>
                      </label>
                    </th>
                    {sessions.map((session) => (
                      <td key={session.id}>
                        <label
                          className={`ops-matrix-cell ${selected.has(`${hall.id}:${session.id}`) ? "checked" : ""}`}
                        >
                          <input
                            type="checkbox"
                            disabled={pending}
                            aria-label={`${hall.name}، ${session.title || "پارت"}، ${clockTime(session.start_time)}`}
                            checked={selected.has(`${hall.id}:${session.id}`)}
                            onChange={() =>
                              toggle([`${hall.id}:${session.id}`])
                            }
                          />
                          <span aria-hidden="true">
                            {selected.has(`${hall.id}:${session.id}`) ? (
                              <Check size={17} />
                            ) : (
                              "+"
                            )}
                          </span>
                        </label>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!halls.length && (
            <p className="ops-muted">سالنی با این نام پیدا نشد.</p>
          )}
          <div className="ops-save-bar">
            <div>
              <strong>{number(selected.size)} تخصیص انتخاب شده</strong>
              <small>پارت‌ها در همهٔ صفحات بر اساس ساعت شروع مرتب‌اند.</small>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                disabled={!dirty || pending}
                onClick={() => {
                  setSelected(new Set(initial));
                  setSaved(false);
                }}
              >
                <RotateCcw size={16} /> بازگردانی
              </button>
              <button
                className="button primary"
                disabled={!dirty || pending}
                onClick={async () => {
                  setPending(true);
                  setError(null);
                  try {
                    await mutate(`organizations/${slug}/assignments/`, "PUT", {
                      assignments: [...selected].map((key) => {
                        const [hall, session] = key.split(":").map(Number);
                        return { hall, session };
                      }),
                    });
                    setSaved(true);
                    onChanged();
                  } catch (error) {
                    setError((error as Error).message);
                  } finally {
                    setPending(false);
                  }
                }}
              >
                <Save size={17} />
                {pending ? "در حال ذخیره…" : "ذخیره تخصیص‌ها"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
