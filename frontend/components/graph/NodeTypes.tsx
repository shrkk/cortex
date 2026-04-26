"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

// ── Course root ───────────────────────────────────────────────────────────────
// UI-SPEC: 60px circle, #C96442 fill, no border, label #FAF7F2 inside
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
          width: 60,
          height: 60,
          borderRadius: "50%",
          background: "#C96442",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          position: "relative",
        }}
      >
        <span style={{
          fontSize: 12,
          fontWeight: 600,
          color: "#FAF7F2",
          textAlign: "center",
          lineHeight: 1.2,
          padding: "0 6px",
          wordBreak: "break-word",
          maxWidth: 52,
        }}>
          {d.label}
        </span>
      </div>
    </>
  );
});

// ── Concept ───────────────────────────────────────────────────────────────────
// UI-SPEC: 32–48px circle scaled by source_count, #3A3832 fill, 1px rgba border
// Struggle signal: box-shadow 0 0 0 3px #EF4444 + cortex-pulse animation (D-04)
// Diameter formula (D-02): d = 32 + min(max(source_count - 1, 0), 4) * 4
//   source_count=1 → 32px; 2 → 36px; 3 → 40px; 4 → 44px; 5+ → 48px
export const ConceptNode = memo(function ConceptNode({ data }: NodeProps) {
  const d = data as {
    label?: string;
    source_count?: number;
    has_struggle?: boolean;
    concept_id?: number;
  };
  const sc = d.source_count ?? 1;
  const diam = 32 + Math.min(Math.max(sc - 1, 0), 4) * 4;

  return (
    <>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top}    style={{ opacity: 0 }} />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
        <div
          role="button"
          aria-label={d.label ?? "Concept"}
          style={{
            width: diam,
            height: diam,
            borderRadius: "50%",
            background: "#3A3832",
            border: "1px solid rgba(255,255,255,0.15)",
            cursor: "pointer",
            position: "relative",
            flexShrink: 0,
            // Struggle ring via box-shadow (D-04: ring only, no fill change)
            boxShadow: d.has_struggle
              ? "0 0 0 3px #EF4444"
              : undefined,
            animation: d.has_struggle
              ? "cortex-pulse 1.5s ease-in-out infinite"
              : undefined,
          }}
        />
        {d.label && (
          <span style={{
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 1.2,
            color: "rgba(250,247,242,0.80)",
            textAlign: "center",
            maxWidth: 80,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            pointerEvents: "none",
          }}>
            {d.label}
          </span>
        )}
      </div>
    </>
  );
});

// ── Flashcard ─────────────────────────────────────────────────────────────────
// UI-SPEC: 40px circle, #2A3D2F fill, #6B8E5A 1.5px solid border (D-05)
export const FlashcardNode = memo(function FlashcardNode({ data }: NodeProps) {
  const d = data as { label?: string };
  return (
    <>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top}    style={{ opacity: 0 }} />
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          background: "#2A3D2F",
          border: "1.5px solid #6B8E5A",
          cursor: "pointer",
        }}
        title={d.label}
      />
    </>
  );
});

// ── Quiz ──────────────────────────────────────────────────────────────────────
// UI-SPEC: 40px circle, #3D2E1F fill, #C18A3F 1.5px dashed border (D-05)
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
          width: 40,
          height: 40,
          borderRadius: "50%",
          background: "#3D2E1F",
          border: "1.5px dashed #C18A3F",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        title="Take Quiz"
      >
        <span style={{ fontSize: 10, fontWeight: 700, color: "#C18A3F" }}>Q</span>
      </div>
    </>
  );
});
