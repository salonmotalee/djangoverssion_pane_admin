"use client";
import { useState } from "react";
import { Archive } from "lucide-react";
import { mutate } from "@/lib/api";
import { InlineError, Modal } from "./ui";

export function ActiveStatus({ active }: { active: boolean }) {
  return (
    <span className={`ops-status ${active ? "active" : "archived"}`}>
      <i />
      {active ? "فعال" : "بایگانی"}
    </span>
  );
}

export function ArchiveDialog({
  title,
  description,
  endpoint,
  onClose,
  onSaved,
}: {
  title: string;
  description: string;
  endpoint: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [pending, setPending] = useState(false),
    [error, setError] = useState<string | null>(null);
  return (
    <Modal
      title={title}
      description={description}
      onClose={() => {
        if (!pending) onClose();
      }}
    >
      <InlineError message={error} />
      <div className="ops-archive-note">
        <Archive size={24} />
        <p>اطلاعات حذف دائمی نمی‌شود و امکان بازیابی وجود دارد.</p>
      </div>
      <div className="modal-footer">
        <button
          className="button secondary"
          disabled={pending}
          onClick={onClose}
        >
          انصراف
        </button>
        <button
          className="button danger"
          disabled={pending}
          onClick={async () => {
            setPending(true);
            try {
              await mutate(endpoint, "DELETE");
              onSaved();
            } catch (error) {
              setError((error as Error).message);
            } finally {
              setPending(false);
            }
          }}
        >
          {pending ? "در حال بایگانی…" : "بایگانی شود"}
        </button>
      </div>
    </Modal>
  );
}
