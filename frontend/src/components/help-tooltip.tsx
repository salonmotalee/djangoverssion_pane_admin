"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CircleHelp } from "lucide-react";
import "../app/ux-refinement.css";

/** Short contextual guidance. Essential warnings belong in the page itself. */
export function HelpTooltip({
  content,
  label = "راهنما",
}: {
  content: string;
  label?: string;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const tooltip = useRef<HTMLSpanElement>(null);
  const touch = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function cancelClose() {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }
  function closeSoon() {
    cancelClose();
    timer.current = setTimeout(() => setOpen(false), 140);
  }
  function show() {
    cancelClose();
    setOpen(true);
  }

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  useLayoutEffect(() => {
    if (!open) return;
    function position() {
      if (!trigger.current || !tooltip.current) return;
      const anchor = trigger.current.getBoundingClientRect();
      const bubble = tooltip.current;
      const width = Math.min(300, window.innerWidth - 32);
      bubble.style.width = `${width}px`;
      const height = bubble.getBoundingClientRect().height;
      const left = Math.max(
        16,
        Math.min(
          window.innerWidth - width - 16,
          anchor.left + anchor.width / 2 - width / 2,
        ),
      );
      const top =
        anchor.bottom + height + 16 < window.innerHeight
          ? anchor.bottom + 8
          : Math.max(8, anchor.top - height - 8);
      bubble.style.left = `${left}px`;
      bubble.style.top = `${top}px`;
      bubble.style.visibility = "visible";
    }
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function dismiss(event: PointerEvent) {
      const target = event.target as Node;
      if (
        !trigger.current?.contains(target) &&
        !tooltip.current?.contains(target)
      )
        setOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        // A help popup inside a dialog should close before its parent dialog.
        event.stopPropagation();
      }
    }
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape, true);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape, true);
    };
  }, [open]);

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className="help-tooltip-trigger"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onPointerDown={(event) => {
          touch.current =
            event.pointerType === "touch" || event.pointerType === "pen";
        }}
        onPointerEnter={(event) => {
          if (event.pointerType === "mouse") show();
        }}
        onPointerLeave={() => {
          if (!touch.current && document.activeElement !== trigger.current)
            closeSoon();
        }}
        onFocus={() => {
          if (!touch.current) show();
        }}
        onBlur={() => {
          touch.current = false;
          cancelClose();
          setOpen(false);
        }}
        onClick={() => {
          cancelClose();
          setOpen((value) => !value);
        }}
      >
        <CircleHelp size={17} aria-hidden="true" />
      </button>
      {open &&
        createPortal(
          <span
            ref={tooltip}
            id={id}
            role="tooltip"
            dir="rtl"
            className="help-tooltip-content"
            onPointerEnter={cancelClose}
            onPointerLeave={() => {
              if (document.activeElement !== trigger.current) closeSoon();
            }}
          >
            {content}
          </span>,
          document.body,
        )}
    </>
  );
}
