"use client";

import { use } from "react";
import useSWR from "swr";
import { apiFetch } from "@/lib/api";
import type { Quiz } from "@/lib/api";
import { QuizView } from "@/components/QuizView";

export default function QuizPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const { data: quiz, error } = useSWR<Quiz>(
    id ? `/quiz/${id}` : null,
    (url: string) => apiFetch<Quiz>(url)
  );

  if (error) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--mastery-low)" }}>
        Quiz generation failed. Make sure this course has processed sources.
      </div>
    );
  }
  if (!quiz) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-muted)" }}>
        Loading quiz…
      </div>
    );
  }

  return (
    <main style={{ minHeight: "100vh", background: "var(--paper)", paddingTop: 24 }}>
      <QuizView quizId={quiz.id} questions={quiz.questions} />
    </main>
  );
}
