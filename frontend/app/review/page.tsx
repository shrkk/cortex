"use client";

import useSWR from "swr";
import { AppShell } from "@/components/AppShell";
import { FlashcardView } from "@/components/FlashcardView";
import { apiFetch, type Flashcard } from "@/lib/api";

const fetcher = (url: string) => apiFetch<Flashcard[]>(url);

export default function ReviewPage() {
  const { data: cards, isLoading } = useSWR<Flashcard[]>(
    "/concepts/struggle-flashcards",
    fetcher as any
  );

  return (
    <AppShell>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        {isLoading ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ fontFamily: "var(--font-serif)", fontSize: 15, color: "var(--ink-muted)" }}>
              Loading…
            </span>
          </div>
        ) : !cards?.length ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ textAlign: "center", maxWidth: "38ch" }}>
              <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, fontWeight: 500, color: "var(--ink)", marginBottom: 10 }}>
                No trouble areas yet
              </div>
              <div style={{ fontSize: 14, color: "var(--ink-muted)", lineHeight: 1.6 }}>
                Flag a concept as a trouble area on the graph to unlock flashcard review.
              </div>
            </div>
          </div>
        ) : (
          <FlashcardView flashcards={cards} />
        )}
      </div>
    </AppShell>
  );
}
