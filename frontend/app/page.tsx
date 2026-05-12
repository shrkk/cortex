"use client";

import { useState } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Eyebrow, Pill } from "@/components/ui/primitives";
import { apiFetch, type Course } from "@/lib/api";

const fetcher = (url: string) => apiFetch<Course[]>(url);

export default function DashboardPage() {
  const router = useRouter();
  const { data: courses, error, mutate } = useSWR("/courses", fetcher);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setSaving(true);
    try {
      const c = await apiFetch<Course>("/courses", {
        method: "POST",
        body: JSON.stringify({ title: name, user_id: 1 }),
      });
      await mutate();
      setCreating(false);
      setNewName("");
      router.push(`/courses/${c.id}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell courses={courses}>
      {creating && (
        <div onClick={() => setCreating(false)} style={{ position: "fixed", inset: 0, background: "var(--backdrop)", zIndex: 50 }}>
          <div onClick={e => e.stopPropagation()} style={{
            position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)",
            background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12,
            padding: "28px 32px", width: 400, boxShadow: "var(--shadow-md)", zIndex: 51,
          }}>
            <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, fontWeight: 500, color: "var(--ink-soft)", marginBottom: 20 }}>New course</div>
            <input
              autoFocus
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleCreate(); if (e.key === "Escape") setCreating(false); }}
              placeholder="e.g. CSE 122, Linear Algebra…"
              style={{
                width: "100%", boxSizing: "border-box", padding: "9px 12px",
                fontFamily: "var(--font-serif)", fontSize: 15,
                border: "1px solid var(--border)", borderRadius: 8,
                background: "var(--paper)", color: "var(--ink)", outline: "none",
                marginBottom: 16,
              }}
            />
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <Button variant="secondary" onClick={() => setCreating(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={saving || !newName.trim()}>
                {saving ? "Creating…" : "Create"}
              </Button>
            </div>
          </div>
        </div>
      )}
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
            <Button icon="plus" onClick={() => setCreating(true)}>New course</Button>
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
