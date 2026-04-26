"use client";

import useSWR from "swr";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Eyebrow, Pill } from "@/components/ui/primitives";
import { apiFetch, type Course } from "@/lib/api";

const fetcher = (url: string) => apiFetch<Course[]>(url);

export default function DashboardPage() {
  const { data: courses, error } = useSWR("/courses", fetcher);

  return (
    <AppShell courses={courses}>
      <div style={{ flex: 1, padding: "40px 48px", overflowY: "auto" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 40 }}>
            <div>
              <Eyebrow style={{ marginBottom: 6 }}>Knowledge graph</Eyebrow>
              <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 40, fontWeight: 500, color: "var(--ink-soft)", letterSpacing: "-0.01em", margin: 0 }}>
                Your courses
              </h1>
              {courses && (
                <div style={{ color: "var(--ink-muted)", fontSize: 13.5, marginTop: 8 }}>
                  {courses.length} course{courses.length !== 1 ? "s" : ""}
                  {courses.some(c => (c.active_struggle_count ?? 0) > 0) && (
                    <> · active struggle signals</>
                  )}
                </div>
              )}
            </div>
            <Button icon="plus">New course</Button>
          </div>

          {/* Course grid */}
          {error && (
            <div style={{ color: "var(--mastery-low)", fontFamily: "var(--font-serif)", fontSize: 15 }}>
              Couldn't load courses. Check that the backend is running at localhost:8000.
            </div>
          )}

          {!error && courses?.length === 0 && <EmptyState />}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
            {courses?.map((c) => (
              <Link key={c.id} href={`/courses/${c.id}`} style={{ textDecoration: "none" }}>
                <Card hoverable padding={24} style={{ height: "100%", boxSizing: "border-box" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 12, height: "100%" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {(c.active_struggle_count ?? 0) > 0 && (
                        <Pill tone="low" dot>{c.active_struggle_count} struggling</Pill>
                      )}
                    </div>
                    <h2 style={{ fontFamily: "var(--font-serif)", fontSize: 20, fontWeight: 500, color: "var(--ink-soft)", margin: 0, lineHeight: 1.3 }}>
                      {c.title}
                    </h2>
                    <div style={{ marginTop: "auto", color: "var(--ink-muted)", fontSize: 12.5, fontFamily: "var(--font-mono)" }}>
                      {c.concept_count ?? 0} concepts
                    </div>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function EmptyState() {
  return (
    <div style={{ padding: "80px 0", textAlign: "center" }}>
      {/* Empty state copy — exact match to UI-SPEC §Empty States: Dashboard */}
      <div style={{ fontSize: 20, fontWeight: 600, color: "var(--ink)", marginBottom: 8 }}>
        No courses yet
      </div>
      <div style={{ color: "var(--ink-muted)", fontSize: 15, maxWidth: "42ch", margin: "0 auto" }}>
        Drop something into the notch to create your first course automatically.
      </div>
    </div>
  );
}
