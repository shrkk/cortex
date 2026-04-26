"use client";

import { use, useState } from "react";
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

  const handleNodeClick = (nodeId: string, nodeType: string) => {
    if (nodeType === "concept") {
      const numId = parseInt(nodeId, 10);
      if (!isNaN(numId)) setSelectedConceptId(numId);
    }
    // quiz node → navigate (handled by link in node or here)
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
      <ReactFlowProvider>
        {graph ? (
          <GraphCanvas graphData={graph} onNodeClick={handleNodeClick} />
        ) : (
          <GraphEmpty />
        )}
      </ReactFlowProvider>

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
