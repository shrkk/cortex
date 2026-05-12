"use client";

import { useRouter } from "next/navigation";
import useSWR from "swr";
import { AppShell } from "@/components/AppShell";
import { apiFetch, type Course } from "@/lib/api";
import { Button, Eyebrow } from "@/components/ui/primitives";

interface QuizSummary {
  id: number;
  course_id: number;
  created_at: string;
  question_count: number;
}

const fetcher = (url: string) => apiFetch<unknown>(url);

export default function QuizIndexPage() {
  const router = useRouter();
  const { data: quizzes, isLoading } = useSWR<QuizSummary[]>("/quiz", fetcher as any);
  const { data: courses } = useSWR<Course[]>("/courses", fetcher as any);

  const courseTitle = (id: number) => courses?.find(c => c.id === id)?.title ?? `Course ${id}`;

  const grouped = quizzes?.reduce<Record<number, QuizSummary[]>>((acc, q) => {
    (acc[q.course_id] ??= []).push(q);
    return acc;
  }, {});

  return (
    <AppShell>
      <div style={{ flex: 1, padding: "40px 48px", maxWidth: 720 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Quiz</Eyebrow>
        <h1 style={{
          fontFamily: "var(--font-serif)", fontSize: 30, fontWeight: 500,
          color: "var(--ink-soft)", letterSpacing: "-0.01em", margin: "0 0 32px",
        }}>
          Exam practice
        </h1>

        {isLoading ? (
          <div style={{ color: "var(--ink-muted)", fontSize: 14 }}>Loading…</div>
        ) : !quizzes?.length ? (
          <div style={{ maxWidth: "40ch" }}>
            <div style={{ fontFamily: "var(--font-serif)", fontSize: 18, color: "var(--ink)", marginBottom: 10 }}>
              No quizzes yet
            </div>
            <div style={{ fontSize: 14, color: "var(--ink-muted)", lineHeight: 1.6 }}>
              Flag a concept as a trouble area on the graph to auto-generate your first quiz, or open a concept and click "Generate quiz".
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {Object.entries(grouped ?? {}).map(([courseId, qs]) => (
              <div key={courseId}>
                <Eyebrow style={{ marginBottom: 12 }}>{courseTitle(Number(courseId))}</Eyebrow>
                <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                  {qs.map((q, i) => (
                    <div
                      key={q.id}
                      style={{
                        display: "flex", alignItems: "center", gap: 16,
                        padding: "14px 16px", borderRadius: 8,
                        border: "1px solid var(--border)",
                        background: i === 0 ? "var(--surface)" : "var(--paper)",
                        cursor: "pointer",
                        transition: "background 150ms",
                      }}
                      onClick={() => router.push(`/quiz/${q.id}`)}
                      onMouseEnter={e => (e.currentTarget.style.background = "var(--surface-hover)")}
                      onMouseLeave={e => (e.currentTarget.style.background = i === 0 ? "var(--surface)" : "var(--paper)")}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ fontFamily: "var(--font-serif)", fontSize: 15, color: "var(--ink)", fontWeight: 500 }}>
                          {i === 0 ? "Latest quiz" : `Quiz ${q.id}`}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--ink-muted)", marginTop: 3 }}>
                          {q.question_count} questions · {new Date(q.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        </div>
                      </div>
                      <span style={{ color: "var(--ink-faint)", fontSize: 16 }}>→</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
