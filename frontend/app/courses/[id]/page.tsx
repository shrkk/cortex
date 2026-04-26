"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { ReactFlowProvider } from "@xyflow/react";
import { AppShell } from "@/components/AppShell";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { ReadingDrawer } from "@/components/ReadingDrawer";
import { Button, Eyebrow } from "@/components/ui/primitives";
import { apiFetch, type Course, type GraphData, type Concept, type Flashcard, type Source } from "@/lib/api";

const fetcher = (url: string) => apiFetch<unknown>(url);

export default function CoursePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [selectedConceptId, setSelectedConceptId] = useState<number | null>(null);

  const { data: course } = useSWR<Course>(`/courses/${id}`, fetcher as any);
  const { data: graphData } = useSWR<GraphData>(`/courses/${id}/graph`, fetcher as any, {
    // Poll while sources are processing (UI-11, D-10)
    refreshInterval: (data) => {
      // Would check sources status here; default to no polling until sources loaded
      return 0;
    },
  });
  const { data: sources } = useSWR<Source[]>(`/courses/${id}/sources`, fetcher as any);
  const { data: concept } = useSWR<Concept>(
    selectedConceptId ? `/concepts/${selectedConceptId}` : null,
    fetcher as any
  );
  const { data: flashcards } = useSWR<Flashcard[]>(
    selectedConceptId ? `/concepts/${selectedConceptId}/flashcards` : null,
    fetcher as any
  );

  // Resolve polling interval based on source statuses (UI-11)
  const hasPending = sources?.some(s => s.status === "pending" || s.status === "processing");
  const { data: liveGraph } = useSWR<GraphData>(
    hasPending ? `/courses/${id}/graph` : null,
    fetcher as any,
    { refreshInterval: 5000 }
  );

  const graph = liveGraph ?? graphData;

  const handleNodeClick = (nodeId: string, nodeType: string, nodeData?: Record<string, unknown>) => {
    if (nodeType === "concept") {
      const conceptId = (nodeData?.concept_id as number) ?? parseInt(nodeId.replace("concept-", ""), 10);
      if (!isNaN(conceptId)) setSelectedConceptId(conceptId);
    }
    if (nodeType === "quiz") {
      const quizId = nodeData?.quiz_id as number | undefined;
      if (quizId) router.push(`/quiz/${quizId}`);
    }
  };

  return (
    <AppShell>
      {/* Page header */}
      <div style={{ padding: "24px 32px 16px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", maxWidth: 1100 }}>
          <div>
            <Eyebrow style={{ marginBottom: 4 }}>Knowledge graph</Eyebrow>
            <h1 style={{ fontFamily: "var(--font-serif)", fontSize: 28, fontWeight: 500, color: "var(--ink-soft)", letterSpacing: "-0.01em", margin: 0 }}>
              {course?.title ?? "Loading…"}
            </h1>
            {graph && (
              <div style={{ color: "var(--ink-muted)", fontSize: 13, marginTop: 6 }}>
                {graph.nodes.filter(n => n.type === "concept").length} concepts
                {" · "}
                {graph.nodes.filter(n => n.type === "concept" && n.data.has_struggle_signals).length} with active struggle signals
                {" · "}
                click a node to read.
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" size="sm">Filter</Button>
            <Button variant="secondary" size="sm" icon="cards">Practice this graph</Button>
          </div>
        </div>
      </div>

      {/* Graph canvas */}
      <div style={{ flex: 1, position: "relative", minHeight: 0 }}>
        <ReactFlowProvider>
          {graph ? (
            <GraphCanvas graphData={graph} onNodeClick={handleNodeClick} />
          ) : (
            <GraphEmpty />
          )}
        </ReactFlowProvider>

        {/* Updating indicator while sources are still processing (UI-SPEC §Graph Polling) */}
        {hasPending && (
          <div style={{
            position: "absolute", bottom: 70, left: 20,
            display: "flex", alignItems: "center", gap: 6,
            fontSize: 12, color: "var(--ink-muted)",
            zIndex: 10,
            background: "rgba(20,18,15,0.85)",
            backdropFilter: "blur(8px)",
            padding: "6px 10px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: "50%",
              background: "var(--mastery-mid)",
              animation: "pulse 1.5s ease-in-out infinite",
              display: "inline-block",
            }} />
            Updating…
          </div>
        )}
      </div>

      {/* Reading drawer */}
      <ReadingDrawer
        concept={concept ?? null}
        flashcards={flashcards ?? []}
        onClose={() => setSelectedConceptId(null)}
      />
    </AppShell>
  );
}

function GraphEmpty() {
  return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--paper)" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontFamily: "var(--font-serif)", fontSize: 20, color: "var(--ink-soft)", marginBottom: 12 }}>
          Nothing in your graph yet.
        </div>
        <div style={{ color: "var(--ink-muted)", fontSize: 15 }}>
          Drop something into the notch to start building this course.
        </div>
      </div>
    </div>
  );
}
