"use client";

import React, { useState, useEffect } from "react";
import type { Flashcard } from "@/lib/api";

interface FlashcardViewProps {
  flashcards: Flashcard[];
  conceptTitle?: string;
}

const TYPE_LABEL: Record<string, string> = {
  definition:  "Definition",
  application: "Application",
  gotcha:      "Gotcha",
  compare:     "Compare",
};

export function FlashcardView({ flashcards, conceptTitle }: FlashcardViewProps) {
  const [idx, setIdx] = useState(0);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => { setFlipped(false); }, [idx]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === " ") { e.preventDefault(); setFlipped(f => !f); }
      if (e.key === "ArrowRight") setIdx(i => Math.min(i + 1, Math.max(flashcards.length - 1, 0)));
      if (e.key === "ArrowLeft")  setIdx(i => Math.max(i - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flashcards.length]);

  if (!flashcards.length) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}>
        <div style={{ textAlign: "center", color: "var(--ink-muted)" }}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>No flashcards yet</div>
          <div style={{ fontSize: 13 }}>Flashcards are generated automatically during ingestion.</div>
        </div>
      </div>
    );
  }

  const card  = flashcards[idx];
  const total = flashcards.length;
  const typeLabel = TYPE_LABEL[card.card_type ?? ""] ?? card.card_type;

  return (
    <div style={{
      flex: 1,
      display: "flex",
      flexDirection: "column",
      padding: "0 48px 40px",
      gap: 0,
      minHeight: 0,
    }}>
      {/* Top bar: progress + concept label */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "24px 0 20px",
        flexShrink: 0,
      }}>
        <span style={{
          fontFamily: "var(--font-mono)",
          fontSize: 13,
          color: "var(--ink-muted)",
          letterSpacing: "0.02em",
        }}>
          {idx + 1} / {total}
        </span>
        {(card.concept_title ?? conceptTitle) && (
          <span style={{
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            color: "var(--ink-muted)",
          }}>
            {card.concept_title ?? conceptTitle} · <span style={{ color: "var(--ink-faint)" }}>flashcards</span>
          </span>
        )}
      </div>

      {/* Card */}
      <div style={{
        flex: 1,
        minHeight: 0,
        background: "var(--paper)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        boxShadow: "var(--shadow-sm)",
        display: "flex",
        flexDirection: "column",
        padding: "28px 36px 32px",
        gap: 0,
        overflow: "hidden",
      }}>
        {/* Type pill + side label */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 28, flexShrink: 0 }}>
          <span style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 99,
            padding: "3px 11px",
            fontFamily: "var(--font-sans)",
            fontSize: 12.5,
            fontWeight: 500,
            color: "var(--ink-soft)",
          }}>
            {typeLabel}
          </span>
          <span style={{
            fontFamily: "var(--font-sans)",
            fontSize: 12.5,
            color: "var(--ink-faint)",
          }}>
            {flipped ? "back" : "front"}
          </span>
        </div>

        {/* Card content */}
        <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div style={{
            fontFamily: "var(--font-serif)",
            fontSize: flipped ? 20 : 34,
            fontWeight: 500,
            lineHeight: 1.4,
            color: "var(--ink)",
            letterSpacing: "-0.015em",
            overflowY: "auto",
          }}>
            {flipped ? card.back : card.front}
          </div>

          {/* Show back button */}
          {!flipped && (
            <div style={{ marginTop: 32, flexShrink: 0 }}>
              <button
                onClick={() => setFlipped(true)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                  color: "var(--ink-soft)",
                  fontFamily: "var(--font-sans)",
                  fontSize: 13.5,
                }}
              >
                Show back
                <kbd style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 5,
                  padding: "2px 7px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--ink-muted)",
                  minWidth: 48,
                }}>
                  space
                </kbd>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Bottom nav */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        paddingTop: 20,
        flexShrink: 0,
      }}>
        <button
          onClick={() => setIdx(i => Math.max(i - 1, 0))}
          disabled={idx === 0}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "transparent",
            border: "none",
            cursor: idx === 0 ? "default" : "pointer",
            color: idx === 0 ? "var(--ink-faint)" : "var(--ink-soft)",
            fontFamily: "var(--font-sans)",
            fontSize: 13.5,
            padding: 0,
          }}
        >
          ← Previous
        </button>

        <span style={{
          fontFamily: "var(--font-sans)",
          fontSize: 12,
          color: "var(--ink-faint)",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}>
          <kbd style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-muted)" }}>space</kbd>
          flip ·
          <kbd style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-muted)" }}>←</kbd>
          <kbd style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 5px", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-muted)" }}>→</kbd>
          navigate
        </span>

        <button
          onClick={() => setIdx(i => Math.min(i + 1, total - 1))}
          disabled={idx === total - 1}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: "transparent",
            border: "none",
            cursor: idx === total - 1 ? "default" : "pointer",
            color: idx === total - 1 ? "var(--ink-faint)" : "var(--ink-soft)",
            fontFamily: "var(--font-sans)",
            fontSize: 13.5,
            padding: 0,
          }}
        >
          Next →
        </button>
      </div>
    </div>
  );
}
