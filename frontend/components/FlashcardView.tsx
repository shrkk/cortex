"use client";

import React, { useEffect, useState } from "react";
import { Button, Eyebrow, Kbd, Pill } from "./ui/primitives";
import type { Flashcard } from "@/lib/api";

interface FlashcardViewProps {
  flashcards: Flashcard[];
  conceptTitle?: string;
  embedded?: boolean; // true when inside ReadingDrawer
}

export function FlashcardView({
  flashcards,
  conceptTitle,
  embedded = false,
}: FlashcardViewProps) {
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);

  const card = flashcards[idx];

  useEffect(() => {
    setRevealed(false);
  }, [idx]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === " ") { e.preventDefault(); setRevealed((r) => !r); }
      if (e.key === "ArrowRight") setIdx((i) => (i + 1) % flashcards.length);
      if (e.key === "ArrowLeft")  setIdx((i) => (i - 1 + flashcards.length) % flashcards.length);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flashcards.length]);

  if (!card) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 48, color: "var(--ink-muted)", fontFamily: "var(--font-serif)", fontSize: 16 }}>
        No flashcards yet.
      </div>
    );
  }

  const TYPE_LABEL: Record<string, string> = {
    definition: "Definition",
    application: "Application",
    gotcha: "Gotcha",
    compare: "Compare",
  };

  const inner = (
    <div style={{ width: "100%", maxWidth: 580, display: "flex", flexDirection: "column", gap: 28 }}>
      {/* Progress */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "var(--ink-muted)", fontSize: 12.5 }}>
        <span style={{ fontFamily: "var(--font-mono)" }}>
          {idx + 1} / {flashcards.length}
        </span>
        <span>
          {conceptTitle ?? "Flashcards"} · flashcards
        </span>
      </div>

      {/* Card face */}
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "44px 40px",
        minHeight: embedded ? 240 : 320,
        display: "flex",
        flexDirection: "column",
        gap: 18,
        boxShadow: "var(--shadow-sm)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Pill tone={card.card_type === "gotcha" ? "mid" : "neutral"}>
            {TYPE_LABEL[card.card_type] ?? "Card"}
          </Pill>
          <span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>front</span>
        </div>

        <div style={{
          fontFamily: "var(--font-serif)",
          fontSize: embedded ? 20 : 26,
          lineHeight: 1.35,
          color: "var(--ink-soft)",
          letterSpacing: "-0.01em",
          fontWeight: 500,
        }}>
          {card.front}
        </div>

        {revealed && (
          <>
            <div style={{ height: 1, background: "var(--border-soft)", margin: "8px 0" }} />
            <span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>back</span>
            {card.card_type === "gotcha" ? (
              <div style={{
                background: "var(--highlight-bg)",
                borderLeft: "3px solid var(--highlight-bar)",
                borderRadius: 6,
                padding: "14px 18px",
                fontFamily: "var(--font-serif)",
                fontSize: 16,
                lineHeight: 1.6,
                color: "var(--ink)",
              }}>
                {card.back}
              </div>
            ) : (
              <div style={{
                fontFamily: "var(--font-serif)",
                fontSize: 17,
                lineHeight: 1.6,
                color: "var(--ink)",
              }}>
                {card.back}
              </div>
            )}
          </>
        )}

        <div style={{ flex: 1 }} />

        <div style={{ display: "flex", justifyContent: "center" }}>
          <button
            onClick={() => setRevealed((r) => !r)}
            style={{
              background: "transparent",
              border: "1px solid var(--border)",
              color: "var(--ink-muted)",
              padding: "9px 16px",
              borderRadius: 6,
              fontFamily: "var(--font-sans)",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {revealed ? "Flip back" : "Show back"} <Kbd>space</Kbd>
          </button>
        </div>
      </div>

      {/* Navigation — flip only, no grading (FLASH-06) */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Button
          variant="ghost"
          icon="arrowLeft"
          onClick={() => setIdx((i) => (i - 1 + flashcards.length) % flashcards.length)}
        >
          Previous
        </Button>
        <span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>
          <Kbd>space</Kbd> flip · <Kbd>←</Kbd>/<Kbd>→</Kbd> navigate
        </span>
        <Button
          variant="secondary"
          onClick={() => setIdx((i) => (i + 1) % flashcards.length)}
        >
          Next card
        </Button>
      </div>
    </div>
  );

  if (embedded) {
    return (
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", padding: "32px 24px", gap: 0 }}>
        {inner}
      </div>
    );
  }

  return (
    <div style={{
      flex: 1,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "48px 24px",
      background: "var(--paper)",
      minHeight: 0,
    }}>
      {inner}
    </div>
  );
}
