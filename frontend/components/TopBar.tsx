"use client";

import { Button, Icon, Kbd } from "./ui/primitives";

export function TopBar({
  onCommandBar,
}: {
  onCommandBar?: () => void;
}) {
  return (
    <header
      style={{
        height: 56,
        background: "var(--paper)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        gap: 24,
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      {/* Wordmark */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        <svg width="22" height="22" viewBox="0 0 64 64" fill="none">
          <circle cx="32" cy="32" r="22" stroke="var(--ink-soft)" strokeWidth="1.6" />
          <path
            d="M14 32 C 14 22, 22 14, 32 14 C 32 22, 32 42, 32 50 C 22 50, 14 42, 14 32 Z"
            stroke="var(--ink-soft)"
            strokeWidth="1.6"
            strokeLinejoin="round"
          />
          <path
            d="M50 32 C 50 22, 42 14, 32 14"
            stroke="var(--ink-soft)"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
          <circle cx="32" cy="32" r="2" fill="var(--ink-soft)" />
        </svg>
        <span
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 19,
            fontWeight: 500,
            color: "var(--ink-soft)",
            letterSpacing: "-0.01em",
          }}
        >
          Cortex
        </span>
      </div>

      {/* Search / command bar trigger */}
      <div style={{ flex: 1, maxWidth: 480, marginLeft: 16 }}>
        <button
          onClick={onCommandBar}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "6px 12px",
            color: "var(--ink-faint)",
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            cursor: "pointer",
            textAlign: "left",
          }}
        >
          <Icon name="search" size={15} />
          <span style={{ flex: 1 }}>Search concepts, sources, anything…</span>
          <Kbd>⌘K</Kbd>
        </button>
      </div>

      <div style={{ flex: 1 }} />

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Button variant="secondary" size="sm" icon="plus">
          Add source
        </Button>
        {/* Avatar placeholder */}
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 999,
            background: "var(--accent-soft)",
            color: "#A54E31",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-serif)",
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          M
        </div>
      </div>
    </header>
  );
}
