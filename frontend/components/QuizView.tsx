"use client";

import React, { useState } from "react";
import type { QuizQuestion, AnswerResponse } from "@/lib/api";
import { apiFetch } from "@/lib/api";

interface QuizViewProps {
  quizId: number;
  questions: QuizQuestion[];
}

export function QuizView({ quizId, questions }: QuizViewProps) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);   // MCQ option index
  const [freeText, setFreeText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [grading, setGrading] = useState<AnswerResponse["grading"] | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [finalResult, setFinalResult] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);

  if (!questions.length) {
    return (
      <div style={{ textAlign: "center", padding: 40, color: "var(--ink-muted)" }}>
        No questions available.
      </div>
    );
  }

  const q = questions[currentIdx];
  const isMcq = q.type === "mcq";

  const canSubmit = !submitted && !loading &&
    (isMcq ? selected !== null : freeText.trim().length > 0);

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setLoading(true);
    try {
      const answer = isMcq
        ? (q.options?.[selected!] ?? String(selected))
        : freeText;
      const result = await apiFetch<AnswerResponse>(`/quiz/${quizId}/answer`, {
        method: "POST",
        body: JSON.stringify({ question_id: q.question_id, answer }),
      });
      setGrading(result.grading);
      setSubmitted(true);
      if (result.is_complete) {
        setIsComplete(true);
        setFinalResult(result);
      }
    } catch (e) {
      console.error("Answer submission failed", e);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    if (currentIdx < questions.length - 1) {
      setCurrentIdx(i => i + 1);
      setSelected(null);
      setFreeText("");
      setSubmitted(false);
      setGrading(null);
    }
  };

  // Final screen
  if (isComplete && finalResult) {
    const correct = finalResult.correct_count ?? 0;
    const total = finalResult.total ?? questions.length;
    return (
      <div style={{
        maxWidth: 640,
        margin: "0 auto",
        padding: "40px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 24,
        alignItems: "center",
      }}>
        <h2 style={{ fontSize: 24, fontWeight: 600, color: "var(--ink)", textAlign: "center" }}>
          {correct} / {total} correct
        </h2>
        {finalResult.concepts_to_review && finalResult.concepts_to_review.length > 0 ? (
          <div style={{ width: "100%", textAlign: "left" }}>
            <p style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-muted)", marginBottom: 8 }}>
              Concepts to review:
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {finalResult.concepts_to_review.map(cid => (
                <span key={cid} style={{
                  fontSize: 12, fontWeight: 600,
                  padding: "4px 10px",
                  borderRadius: "var(--radius-pill)",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  color: "var(--ink-soft)",
                }}>
                  Concept #{cid}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: "center" }}>
            <p style={{ fontSize: 16, fontWeight: 600, color: "var(--mastery-high)", marginBottom: 4 }}>
              Great work
            </p>
            <p style={{ fontSize: 14, color: "var(--ink-muted)" }}>
              No weak spots identified from this quiz.
            </p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "40px 16px" }}>
      {/* Progress */}
      <div style={{
        height: 4,
        background: "var(--surface)",
        borderRadius: 2,
        marginBottom: 32,
        overflow: "hidden",
      }}>
        <div style={{
          height: "100%",
          width: `${((currentIdx + 1) / questions.length) * 100}%`,
          background: "var(--accent)",
          transition: "width 0.3s var(--ease)",
        }} />
      </div>

      {/* Question number */}
      <p style={{ fontSize: 12, color: "var(--ink-muted)", marginBottom: 8, fontWeight: 600 }}>
        Question {currentIdx + 1} of {questions.length}
      </p>

      {/* Question text */}
      <p style={{ fontSize: 18, fontWeight: 600, color: "var(--ink)", marginBottom: 24, lineHeight: 1.4 }}>
        {q.question}
      </p>

      {/* MCQ options */}
      {isMcq && q.options && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
          {q.options.map((opt, i) => (
            <label
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 14px",
                background: selected === i ? "var(--accent-soft)" : "var(--surface)",
                border: `1px solid ${selected === i ? "var(--accent)" : "var(--border)"}`,
                borderRadius: "var(--radius-sm)",
                cursor: submitted ? "default" : "pointer",
                fontSize: 14,
                color: "var(--ink)",
                transition: "all var(--dur-fast) var(--ease)",
              }}
            >
              <input
                type="radio"
                name="mcq"
                value={i}
                checked={selected === i}
                onChange={() => !submitted && setSelected(i)}
                disabled={submitted}
                style={{ accentColor: "var(--accent)" }}
              />
              {opt}
            </label>
          ))}
        </div>
      )}

      {/* Free-response textarea */}
      {!isMcq && (
        <textarea
          value={freeText}
          onChange={e => setFreeText(e.target.value)}
          disabled={submitted}
          placeholder="Type your answer..."
          rows={3}
          style={{
            width: "100%",
            padding: "10px 14px",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            fontSize: 14,
            color: "var(--ink)",
            resize: "vertical",
            marginBottom: 16,
            boxSizing: "border-box",
          }}
        />
      )}

      {/* Submit button */}
      {!submitted && (
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          style={{
            padding: "10px 24px",
            background: canSubmit ? "var(--accent)" : "var(--surface)",
            color: canSubmit ? "var(--accent-ink)" : "var(--ink-faint)",
            border: `1px solid ${canSubmit ? "var(--accent)" : "var(--border)"}`,
            borderRadius: "var(--radius-sm)",
            fontSize: 14,
            fontWeight: 600,
            cursor: canSubmit ? "pointer" : "not-allowed",
          }}
        >
          {loading ? "Grading…" : "Submit Answer"}
        </button>
      )}

      {/* Feedback after submit */}
      {submitted && grading && (
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{
            padding: "12px 16px",
            borderRadius: "var(--radius-sm)",
            background: grading.correct ? "var(--success-soft)" : "var(--danger-soft)",
            border: `1px solid ${grading.correct ? "var(--mastery-high)" : "var(--mastery-low)"}`,
            fontSize: 14,
            color: grading.correct ? "var(--mastery-high)" : "var(--mastery-low)",
            fontWeight: 600,
          }}>
            {grading.correct ? "✓ Correct" : "✗ Incorrect"}
          </div>
          <p style={{ fontSize: 14, color: "var(--ink-muted)", lineHeight: 1.6 }}>
            {grading.feedback}
          </p>
          {!isComplete && currentIdx < questions.length - 1 && (
            <button
              onClick={handleNext}
              style={{
                alignSelf: "flex-start",
                padding: "8px 20px",
                background: "var(--surface)",
                color: "var(--ink)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Next Question →
            </button>
          )}
        </div>
      )}
    </div>
  );
}
