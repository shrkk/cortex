"use client";

import React, { useState, useEffect } from "react";
import type { Flashcard } from "@/lib/api";

interface FlashcardViewProps {
  flashcards: Flashcard[];
  conceptTitle?: string;
  embedded?: boolean;
  onBack?: () => void;
}

export function FlashcardView({ flashcards, conceptTitle, embedded, onBack }: FlashcardViewProps) {
  const [idx, setIdx] = useState(0);
  const [flipped, setFlipped] = useState(false);

  // Reset flip state when card changes
  useEffect(() => { setFlipped(false); }, [idx]);

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === " ") { e.preventDefault(); setFlipped(f => !f); }
      if (e.key === "ArrowRight") {
        setIdx(i => (i + 1) % Math.max(flashcards.length, 1));
      }
      if (e.key === "ArrowLeft") {
        setIdx(i => (i - 1 + Math.max(flashcards.length, 1)) % Math.max(flashcards.length, 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flashcards.length]);

  if (!flashcards.length) {
    return (
      <div style={{ padding: 24, color: "var(--ink-muted)", textAlign: "center" }}>
        <p style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>No flashcards yet</p>
        <p style={{ fontSize: 14 }}>Flashcards are generated automatically when concept extraction completes.</p>
      </div>
    );
  }

  const card = flashcards[idx];
  const total = flashcards.length;

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: 16,
      padding: embedded ? "0" : "32px 16px",
      width: "100%",
    }}>
      {/* Back button when embedded in panel */}
      {embedded && onBack && (
        <button
          onClick={onBack}
          style={{
            alignSelf: "flex-start",
            background: "none",
            border: "none",
            color: "var(--ink-muted)",
            fontSize: 13,
            cursor: "pointer",
            padding: "4px 0",
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          ← Back
          {conceptTitle && <span style={{ color: "var(--ink-faint)" }}>to {conceptTitle}</span>}
        </button>
      )}

      {/* Progress */}
      <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
        {idx + 1} / {total}
      </div>

      {/* Card with 3D flip */}
      {/* The card wrapper is 480x280 with perspective from .flashcard-container */}
      <div
        className="flashcard-container"
        style={{
          width: Math.min(480, embedded ? 320 : 480),
          height: embedded ? 200 : 280,
        }}
      >
        <div className={`flashcard-inner${flipped ? " flipped" : ""}`}
          style={{ width: "100%", height: "100%" }}
        >
          {/* Front face */}
          <div
            className="flashcard-front"
            style={{ background: "var(--surface)", cursor: "pointer" }}
            onClick={() => setFlipped(true)}
          >
            <span style={{ fontSize: embedded ? 18 : 24, fontWeight: 600, textAlign: "center", color: "var(--ink)", lineHeight: 1.3 }}>
              {card.front}
            </span>
          </div>
          {/* Back face */}
          <div
            className="flashcard-back"
            style={{ background: "var(--surface)" }}
          >
            <span style={{ fontSize: 14, fontWeight: 400, textAlign: "center", color: "var(--ink-soft)", lineHeight: 1.6 }}>
              {card.back}
            </span>
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {!flipped ? (
          <button
            onClick={() => setFlipped(true)}
            style={{
              padding: "8px 20px",
              background: "var(--accent)",
              color: "var(--accent-ink)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Show Answer
          </button>
        ) : (
          <button
            onClick={() => setIdx(i => (i + 1) % total)}
            style={{
              padding: "8px 20px",
              background: "var(--surface-hover)",
              color: "var(--ink)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Next →
          </button>
        )}
      </div>

      {/* Card type badge */}
      {card.card_type && (
        <span style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--ink-faint)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}>
          {card.card_type}
        </span>
      )}
    </div>
  );
}
