"use client";

import React, { useState } from "react";
import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { Icon, Kbd } from "./ui/primitives";
import type { Course } from "@/lib/api";

export function AppShell({
  children,
  courses,
}: {
  children: React.ReactNode;
  courses?: Course[];
}) {
  const [cmdOpen, setCmdOpen] = useState(false);

  return (
    <div style={{ minHeight: "100vh", background: "var(--paper)" }}>
      <TopBar onCommandBar={() => setCmdOpen(true)} />
      <div style={{ display: "flex", minHeight: "calc(100vh - 56px)" }}>
        <Sidebar courses={courses} />
        <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, minHeight: 0 }}>
          {children}
        </main>
      </div>

      {cmdOpen && <CommandBar onClose={() => setCmdOpen(false)} />}
    </div>
  );
}

function CommandBar({ onClose }: { onClose: () => void }) {
  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "var(--backdrop)",
          zIndex: 60,
        }}
      />
      <div
        style={{
          position: "fixed",
          top: "20vh",
          left: "50%",
          transform: "translateX(-50%)",
          width: "100%",
          maxWidth: 560,
          zIndex: 61,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          boxShadow: "var(--shadow-lg)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "14px 18px",
            borderBottom: "1px solid var(--border-soft)",
          }}
        >
          <Icon name="search" size={16} color="var(--ink-muted)" />
          <input
            autoFocus
            placeholder="Search concepts, sources, anything…"
            style={{
              flex: 1,
              border: 0,
              background: "transparent",
              outline: "none",
              fontFamily: "var(--font-sans)",
              fontSize: 15,
              color: "var(--ink)",
            }}
          />
          <Kbd>esc</Kbd>
        </div>
        <div style={{ padding: "8px 8px 12px" }}>
          <div style={{ padding: "6px 12px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--ink-muted)", fontWeight: 500 }}>
            Recent concepts
          </div>
          {["Open a course to see concepts here"].map((t) => (
            <div
              key={t}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "8px 12px",
                borderRadius: 6,
                cursor: "pointer",
                color: "var(--ink-muted)",
                fontSize: 14,
              }}
            >
              <Icon name="brain" size={15} color="var(--ink-muted)" />
              <span style={{ fontFamily: "var(--font-serif)", fontSize: 14.5, color: "var(--ink-soft)" }}>
                {t}
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
