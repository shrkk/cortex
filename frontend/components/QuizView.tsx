"use client";

import React, { useEffect, useState } from "react";
import { Button, Eyebrow, Icon } from "./ui/primitives";
import type { QuizQuestion } from "@/lib/api";

interface QuizViewProps {
  questions: QuizQuestion[];
  onComplete?: (score: number, total: number, weakConcepts: string[]) => void;
}

export function QuizView({ questions, onComplete }: QuizViewProps) {
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [freeText, setFreeText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [results, setResults] = useState<boolean[]>([]);
  const [done, setDone] = useState(false);

  const q = questions[idx];

  useEffect(() => {
    setSelected(null);
    setFreeText("");
    setSubmitted(false);
  }, [idx]);

  const handleSubmit = () => {
    setSubmitted(true);
    if (q.type === "mcq") {
      setResults((r) => [...r, selected === q.correct_index]);
    } else {
      setResults((r) => [...r, true]); // free text — marked as attempted
    }
  };

  const handleNext = () => {
    if (idx < questions.length - 1) {
      setIdx((i) => i + 1);
    } else {
      setDone(true);
      const score = results.filter(Boolean).length + (q.type === "mcq" && selected === q.correct_index ? 1 : 0);
      onComplete?.(score, questions.length, []);
    }
  };

  if (done || !q) {
    const score = results.filter(Boolean).length;
    return <QuizResults score={score} total={questions.length} />;
  }

  const progress = (idx / questions.length) * 100;
  const canSubmit =
    q.type === "mcq" ? selected !== null : freeText.trim().length > 0;

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "40px 24px",
        background: "var(--paper)",
        overflowY: "auto",
      }}
    >
      <div style={{ width: "100%", maxWidth: 640, display: "flex", flexDirection: "column", gap: 28 }}>
        {/* Progress bar */}
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 8,
              color: "var(--ink-muted)",
              fontSize: 12.5,
            }}
          >
            <span>Question {idx + 1} of {questions.length}</span>
          </div>
          <div
            style={{
              height: 3,
              background: "var(--surface-sunken)",
              borderRadius: 999,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${progress}%`,
                height: "100%",
                background: "var(--accent)",
                transition: "width 300ms var(--ease)",
              }}
            />
          </div>
        </div>

        {/* Question */}
        <div>
          <div
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 24,
              lineHeight: 1.35,
              color: "var(--ink-soft)",
              letterSpacing: "-0.01em",
              fontWeight: 500,
            }}
          >
            {q.question}
          </div>
        </div>

        {/* MCQ options */}
        {q.type === "mcq" && q.options && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {q.options.map((opt, i) => {
              const isSel = selected === i;
              const isCorrect = submitted && i === q.correct_index;
              const isWrong = submitted && isSel && i !== q.correct_index;
              return (
                <button
                  key={i}
                  onClick={() => !submitted && setSelected(i)}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 14,
                    background: isCorrect
                      ? "var(--mastery-high-soft)"
                      : isWrong
                      ? "var(--mastery-low-soft)"
                      : isSel
                      ? "var(--surface-hover)"
                      : "var(--surface)",
                    border: `1px solid ${
                      isCorrect
                        ? "var(--mastery-high)"
                        : isWrong
                        ? "var(--mastery-low)"
                        : isSel
                        ? "var(--border-strong)"
                        : "var(--border)"
                    }`,
                    borderRadius: 8,
                    padding: "14px 18px",
                    textAlign: "left",
                    cursor: submitted ? "default" : "pointer",
                    fontFamily: "var(--font-sans)",
                    color: "var(--ink)",
                    transition: "background 200ms var(--ease), border-color 200ms var(--ease)",
                  }}
                >
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 999,
                      flexShrink: 0,
                      border: `1px solid ${isSel ? "var(--accent)" : "var(--border-strong)"}`,
                      background:
                        isSel && !submitted ? "var(--accent)" : "transparent",
                      color: "var(--accent-ink)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      fontWeight: 500,
                      marginTop: 1,
                    }}
                  >
                    {String.fromCharCode(65 + i)}
                  </span>
                  <span style={{ fontSize: 15, lineHeight: 1.5, flex: 1 }}>{opt}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Free response */}
        {(q.type === "short_answer" || q.type === "application") && (
          <textarea
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            disabled={submitted}
            placeholder="Type your answer."
            style={{
              minHeight: 140,
              width: "100%",
              boxSizing: "border-box",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "14px 16px",
              fontFamily: "var(--font-serif)",
              fontSize: 16,
              lineHeight: 1.6,
              color: "var(--ink)",
              resize: "vertical",
              outline: "none",
            }}
          />
        )}

        {/* Explanation — shown after submit if grading feedback available */}
        {submitted && q.grading?.feedback && (
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "16px 20px",
            }}
          >
            <Eyebrow style={{ marginBottom: 6 }}>Feedback</Eyebrow>
            <div
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 14.5,
                lineHeight: 1.6,
                color: "var(--ink)",
              }}
            >
              {q.grading.feedback}
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{ display: "flex", gap: 8, justifyContent: "space-between" }}>
          <Button variant="ghost" icon="arrowLeft">
            Skip
          </Button>
          {submitted ? (
            <Button onClick={handleNext}>
              Next question <Icon name="arrowRight" size={15} />
            </Button>
          ) : (
            <Button disabled={!canSubmit} onClick={handleSubmit}>
              Submit answer
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function QuizResults({
  score,
  total,
}: {
  score: number;
  total: number;
}) {
  const missed = total - score;
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "64px 24px",
        background: "var(--paper)",
      }}
    >
      <div style={{ maxWidth: 480, width: "100%", textAlign: "center", display: "flex", flexDirection: "column", gap: 16 }}>
        <div
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 56,
            fontWeight: 400,
            color: "var(--ink-soft)",
            letterSpacing: "-0.02em",
            lineHeight: 1,
          }}
        >
          {score} of {total}
        </div>
        <div style={{ color: "var(--ink-muted)", fontSize: 15 }}>
          {missed === 0
            ? "All concepts answered correctly."
            : `${missed} concept${missed > 1 ? "s" : ""} to revisit.`}
        </div>
      </div>
    </div>
  );
}
