"use client";

import React, { useState } from "react";
import { Button, Card, Eyebrow, Icon, Pill } from "./ui/primitives";
import { FlashcardView } from "./FlashcardView";
import type { Concept, Flashcard } from "@/lib/api";

interface ReadingDrawerProps {
  concept: Concept | null;
  flashcards?: Flashcard[];
  onClose: () => void;
  onGenerateQuiz?: () => void;
}

export function ReadingDrawer({
  concept,
  flashcards = [],
  onClose,
  onGenerateQuiz,
}: ReadingDrawerProps) {
  const [mode, setMode] = useState<"detail" | "flashcards">("detail");

  if (!concept) return null;

  // struggle_signals is Record<string, unknown> | null — not an array
  const hasStruggle =
    concept.struggle_signals != null && Object.keys(concept.struggle_signals).length > 0;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "var(--backdrop)",
          zIndex: 50,
          animation: "fadeIn 200ms var(--ease)",
        }}
      />

      {/* Drawer */}
      <aside
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: 480,
          background: "var(--surface)",
          borderLeft: "1px solid var(--border)",
          boxShadow: "var(--shadow-md)",
          zIndex: 51,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          animation: "slideInRight 300ms var(--ease)",
        }}
      >
        {/* Sticky header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "16px 24px",
            borderBottom: "1px solid var(--border)",
            position: "sticky",
            top: 0,
            background: "var(--surface)",
            zIndex: 1,
          }}
        >
          {mode === "flashcards" ? (
            <button
              onClick={() => setMode("detail")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                border: 0,
                background: "transparent",
                color: "var(--ink-muted)",
                fontFamily: "var(--font-sans)",
                fontSize: 13,
                cursor: "pointer",
                padding: "4px 0",
              }}
            >
              <Icon name="arrowLeft" size={14} />
              Back
            </button>
          ) : hasStruggle ? (
            <Pill tone="low" dot>
              Struggle signals active
            </Pill>
          ) : (
            <Pill tone="neutral" dot>
              Concept
            </Pill>
          )}
          <div style={{ flex: 1 }} />
          <button
            onClick={onClose}
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              border: 0,
              background: "transparent",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--ink-muted)",
              cursor: "pointer",
            }}
          >
            <Icon name="close" size={16} />
          </button>
        </div>

        {/* Panel body — detail or flashcards in-place (D-07) */}
        {mode === "flashcards" ? (
          <FlashcardView
            flashcards={flashcards}
            conceptTitle={concept.title}
            embedded
          />
        ) : (
          <ConceptDetail
            concept={concept}
            onViewFlashcards={() => setMode("flashcards")}
            onGenerateQuiz={onGenerateQuiz}
          />
        )}
      </aside>
    </>
  );
}

function ConceptDetail({
  concept,
  onViewFlashcards,
  onGenerateQuiz,
}: {
  concept: Concept;
  onViewFlashcards: () => void;
  onGenerateQuiz?: () => void;
}) {
  // struggle_signals is Record<string, unknown> | null — not an array
  const hasStruggle =
    concept.struggle_signals != null && Object.keys(concept.struggle_signals).length > 0;

  return (
    <div
      style={{
        padding: "28px 32px 40px",
        display: "flex",
        flexDirection: "column",
        gap: 24,
      }}
    >
      {/* Title */}
      <div>
        <Eyebrow style={{ marginBottom: 6 }}>Concept</Eyebrow>
        <h1
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 32,
            color: "var(--ink-soft)",
            fontWeight: 500,
            letterSpacing: "-0.01em",
            margin: 0,
            lineHeight: 1.2,
          }}
        >
          {concept.title}
        </h1>
        <div
          style={{
            display: "flex",
            gap: 14,
            marginTop: 12,
            color: "var(--ink-muted)",
            fontSize: 12.5,
          }}
        >
          <span>{concept.flashcard_count ?? 0} flashcards</span>
        </div>
      </div>

      {/* Summary */}
      {concept.summary && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Definition</Eyebrow>
          <p
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 16,
              lineHeight: 1.65,
              color: "var(--ink)",
              maxWidth: "60ch",
            }}
          >
            {concept.summary}
          </p>
        </div>
      )}

      {/* Gotchas — amber highlight bar (UI-05) */}
      {concept.gotchas && concept.gotchas.length > 0 && (
        <div
          style={{
            background: "var(--highlight-bg)",
            borderLeft: "3px solid var(--highlight-bar)",
            borderRadius: 6,
            padding: "14px 18px",
          }}
        >
          <Eyebrow style={{ color: "#7A5524", marginBottom: 6 }}>Gotchas</Eyebrow>
          <ul
            style={{
              margin: 0,
              paddingLeft: 18,
              color: "var(--ink-soft)",
              fontFamily: "var(--font-serif)",
              fontSize: 14.5,
              lineHeight: 1.6,
            }}
          >
            {concept.gotchas.map((g, i) => (
              <li key={i} style={{ marginBottom: i < concept.gotchas!.length - 1 ? 4 : 0 }}>
                {g}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Key points */}
      {concept.key_points && concept.key_points.length > 0 && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Key points</Eyebrow>
          <ul
            style={{
              margin: 0,
              paddingLeft: 18,
              color: "var(--ink)",
              fontFamily: "var(--font-serif)",
              fontSize: 14.5,
              lineHeight: 1.65,
            }}
          >
            {concept.key_points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Examples */}
      {concept.examples && concept.examples.length > 0 && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Examples</Eyebrow>
          <ul
            style={{
              margin: 0,
              paddingLeft: 18,
              color: "var(--ink)",
              fontFamily: "var(--font-serif)",
              fontSize: 14.5,
              lineHeight: 1.65,
            }}
          >
            {concept.examples.map((ex, i) => (
              <li key={i}>{ex}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Struggle signals — backend returns dict (not array); iterate Object.entries */}
      {hasStruggle && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Struggle signals</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {Object.entries(concept.struggle_signals!).map(([key, val], i) => (
              <Card key={i} padding={14} style={{ background: "var(--paper)" }}>
                <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 999,
                      background: "var(--mastery-low)",
                      marginTop: 7,
                      flexShrink: 0,
                    }}
                  />
                  <div>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: "var(--ink-soft)",
                      }}
                    >
                      {key}
                    </div>
                    <div
                      style={{
                        fontSize: 12.5,
                        color: "var(--ink-muted)",
                        lineHeight: 1.5,
                        marginTop: 2,
                      }}
                    >
                      {typeof val === "string" ? val : JSON.stringify(val)}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Student questions */}
      {concept.student_questions && concept.student_questions.length > 0 && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Student questions</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {concept.student_questions.map((q, i) => (
              <div
                key={i}
                style={{
                  fontFamily: "var(--font-serif)",
                  fontStyle: "italic",
                  color: "var(--ink-soft)",
                  fontSize: 14,
                  lineHeight: 1.55,
                  paddingLeft: 12,
                  borderLeft: "2px solid var(--border)",
                }}
              >
                {q}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sources */}
      {concept.source_citations && concept.source_citations.length > 0 && (
        <div>
          <Eyebrow style={{ marginBottom: 10 }}>Sources</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {concept.source_citations.map((s, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 0",
                  borderTop: i > 0 ? "1px solid var(--border-soft)" : undefined,
                }}
              >
                <div
                  style={{
                    width: 28,
                    height: 34,
                    border: "1px solid var(--border)",
                    borderRadius: 3,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: "var(--font-mono)",
                    fontSize: 8.5,
                    color: "var(--ink-muted)",
                    background: "var(--paper)",
                    flexShrink: 0,
                  }}
                >
                  {s.source_type}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: 14,
                      color: "var(--ink-soft)",
                      fontWeight: 500,
                    }}
                  >
                    {s.title ?? `Source ${s.source_id}`}
                  </div>
                </div>
                <Icon name="arrowRight" size={14} color="var(--ink-faint)" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, paddingTop: 8 }}>
        <Button icon="cards" onClick={onViewFlashcards}>
          View flashcards
        </Button>
        <Button variant="secondary" onClick={onGenerateQuiz}>
          Generate quiz
        </Button>
      </div>
    </div>
  );
}
