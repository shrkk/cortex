"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

// ── Course root ───────────────────────────────────────────────────────────────
// Dark circle on the light canvas, serif wordmark inside
export const CourseNode = memo(function CourseNode({ data }: NodeProps) {
  const d = data as { label?: string };
  return (
    <>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top}    style={{ opacity: 0 }} />
      <div
        role="button"
        aria-label={d.label ?? "Course"}
        style={{
          width: 200,
          height: 200,
          borderRadius: "50%",
          background: "var(--ink-soft)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center", 
          cursor: "grab",
        }}
      >
        <span style={{
          fontFamily: "var(--font-serif)",
          fontSize: 16,
          fontWeight: 500,
          color: "var(--paper)",
          textAlign: "center",
          lineHeight: 1.25,
          padding: "0 18px",
          letterSpacing: "-0.01em",
        }}>
          {d.label}
        </span>
      </div>
    </>
  );
});

// ── Concept ───────────────────────────────────────────────────────────────────
// Light surface circle, serif label inside, struggle = mastery-low border + pulse dot
// Struggle nodes with flashcards show a small count badge at bottom-right
export const ConceptNode = memo(function ConceptNode({ data }: NodeProps) {
  const d = data as {
    label?: string;
    source_count?: number;
    has_struggle?: boolean;
    flashcard_count?: number;
    concept_id?: number;
  };
  const sc = d.source_count ?? 1;
  // 110–130px: large circles so labels are readable
  const diam = 110 + Math.min(Math.max(sc - 1, 0), 4) * 5;
  const showFlashcardBadge = d.has_struggle && (d.flashcard_count ?? 0) > 0;

  return (
    <>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top}    style={{ opacity: 0 }} />
      <div
        role="button"
        aria-label={d.label ?? "Concept"}
        style={{
          width: diam,
          height: diam,
          borderRadius: "50%",
          background: "var(--surface)",
          border: d.has_struggle
            ? "1.5px solid var(--mastery-low)"
            : "1.5px solid var(--border-strong)",
          cursor: "grab",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
          transition: "border-color 200ms var(--ease), background 200ms var(--ease)",
          boxShadow: d.has_struggle
            ? "0 0 0 3px var(--mastery-low-soft)"
            : "var(--shadow-xs)",
          animation: d.has_struggle ? "cortex-pulse 1.5s ease-in-out infinite" : undefined,
        }}
      >
        {d.has_struggle && (
          <span style={{
            position: "absolute",
            top: 6,
            right: 6,
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "var(--mastery-low)",
            boxShadow: "0 0 0 2px var(--surface)",
          }} />
        )}
        {d.label && (
          <span style={{
            fontFamily: "var(--font-serif)",
            fontSize: Math.max(12, Math.min(15, diam * 0.125)),
            fontWeight: 500,
            lineHeight: 1.25,
            color: "var(--ink-soft)",
            textAlign: "center",
            padding: "0 10px",
            display: "-webkit-box",
            WebkitLineClamp: 4,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            pointerEvents: "none",
            letterSpacing: "-0.005em",
          }}>
            {d.label}
          </span>
        )}
        {showFlashcardBadge && (
          <span style={{
            position: "absolute",
            bottom: -8,
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--accent)",
            color: "var(--accent-ink)",
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.02em",
            padding: "2px 7px",
            borderRadius: 99,
            pointerEvents: "none",
            whiteSpace: "nowrap",
            boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
          }}>
            {d.flashcard_count}
          </span>
        )}
      </div>
    </>
  );
});


// ── Quiz ──────────────────────────────────────────────────────────────────────
// Solid accent-filled pill, sans bold white label
export const QuizNode = memo(function QuizNode({ data }: NodeProps) {
  const d = data as { label?: string; quiz_id?: number };
  return (
    <>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top}    style={{ opacity: 0 }} />
      <div
        role="button"
        aria-label="Quiz"
        style={{
          padding: "9px 16px",
          borderRadius: 6,
          background: "var(--accent)",
          border: "1.5px solid var(--accent)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minWidth: 110,
          whiteSpace: "nowrap",
          transition: "background 200ms var(--ease)",
        }}
        title="Take quiz"
      >
        <span style={{
          fontFamily: "var(--font-sans)",
          fontSize: 13,
          fontWeight: 600,
          color: "var(--accent-ink)",
          letterSpacing: "0",
        }}>
          {d.label ?? "Weak-spot quiz"}
        </span>
      </div>
    </>
  );
});
