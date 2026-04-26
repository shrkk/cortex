"use client";

import React, { useCallback, useEffect } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  BaseEdge,
  getStraightPath,
  type EdgeProps,
} from "@xyflow/react";

type FlowNode = Node<Record<string, unknown>>;
type FlowEdge = Edge<Record<string, unknown>>;
import "@xyflow/react/dist/style.css";
import * as dagre from "@dagrejs/dagre";
import { CourseNode, ConceptNode, FlashcardNode, QuizNode } from "./NodeTypes";
import type { GraphData, GraphNode } from "@/lib/api";

// nodeTypes MUST be defined outside the component body — prevents object recreation
const nodeTypes: NodeTypes = {
  course:    CourseNode,
  concept:   ConceptNode,
  flashcard: FlashcardNode,
  quiz:      QuizNode,
};

// ── Edge styles per type ───────────────────────────────────────────────────────
const EDGE_STYLE: Record<
  string,
  { stroke: string; strokeWidth: number; strokeDasharray?: string; opacity: number; arrow: boolean }
> = {
  contains:      { stroke: "var(--border-strong)", strokeWidth: 2.4, opacity: 0.85, arrow: false },
  prerequisite:  { stroke: "var(--ink-muted)",     strokeWidth: 1.4, opacity: 0.85, arrow: true  },
  co_occurrence: { stroke: "var(--ink-muted)",     strokeWidth: 1.0, strokeDasharray: "5 4", opacity: 0.55, arrow: false },
  related:       { stroke: "var(--ink-muted)",     strokeWidth: 1.0, strokeDasharray: "1 4", opacity: 0.55, arrow: false },
  flashcard_of:  { stroke: "var(--accent)",        strokeWidth: 1.0, strokeDasharray: "2 3", opacity: 0.65, arrow: false },
  quiz_of:       { stroke: "var(--accent)",        strokeWidth: 1.4, opacity: 0.85, arrow: false },
};

function CortexEdge({ id, sourceX, sourceY, targetX, targetY, data }: EdgeProps) {
  const edgeType = (data as { edge_type?: string })?.edge_type ?? "related";
  const s = EDGE_STYLE[edgeType] ?? EDGE_STYLE.related;
  const [edgePath] = getStraightPath({ sourceX, sourceY, targetX, targetY });
  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{
        stroke: s.stroke,
        strokeWidth: s.strokeWidth,
        strokeDasharray: s.strokeDasharray,
        opacity: s.opacity,
      }}
      markerEnd={s.arrow ? `url(#arrow-pre)` : undefined}
    />
  );
}

const edgeTypes: EdgeTypes = { cortex: CortexEdge };

// ── Dagre layout ──────────────────────────────────────────────────────────────
function nodeSize(nodeType: string, sourceCount = 1) {
  if (nodeType === "course")    return { w: 132, h: 132 };
  if (nodeType === "flashcard") return { w: 80,  h: 28  };
  if (nodeType === "quiz")      return { w: 140, h: 40  };
  const d = 50 + Math.min(sourceCount, 12) * 5;
  return { w: d, h: d };
}

function buildLayout(rawNodes: GraphNode[], rawEdges: GraphData["edges"]) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 80, marginx: 48, marginy: 48 });

  rawNodes.forEach((n) => {
    // Backend: n.type at root, n.data.source_count nested
    const { w, h } = nodeSize(n.type, n.data.source_count);
    g.setNode(n.id, { width: w, height: h });
  });
  rawEdges.forEach((e) => {
    g.setEdge(e.source, e.target);
  });
  dagre.layout(g);

  const nodes: Node[] = rawNodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: n.type,                          // FIX: was n.node_type — backend uses "type" at root
      position: { x: pos.x - pos.width / 2, y: pos.y - pos.height / 2 },
      data: {
        label:           n.data.label,        // FIX: was n.label — backend nests in data
        source_count:    n.data.source_count,
        has_struggle:    n.data.has_struggle_signals,  // FIX: was has_struggle — backend uses has_struggle_signals
        flashcard_count: n.data.flashcard_count,
        concept_id:      n.data.concept_id,
        quiz_id:         n.data.quiz_id,
        flashcard_id:    n.data.flashcard_id,
        course_id:       n.data.course_id,
      },
    };
  });

  const edges: Edge[] = rawEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: "cortex",
    data: { edge_type: e.type },  // FIX: was e.edge_type — backend uses "type" at root
  }));

  return { nodes, edges };
}

// ── Component ─────────────────────────────────────────────────────────────────
export function GraphCanvas({
  graphData,
  onNodeClick,
}: {
  graphData: GraphData | null | undefined;
  onNodeClick?: (nodeId: string, nodeType: string) => void;
}) {
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([]);
  const { fitView } = useReactFlow();
  const didLayout = React.useRef(false);

  useEffect(() => {
    if (!graphData?.nodes?.length) return;
    const { nodes: ln, edges: le } = buildLayout(graphData.nodes, graphData.edges);
    setNodes(ln);
    setEdges(le);
    if (!didLayout.current) {
      didLayout.current = true;
      setTimeout(() => fitView({ padding: 0.12 }), 0);
    }
  }, [graphData, setNodes, setEdges, fitView]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.id, node.type ?? "concept");
    },
    [onNodeClick]
  );

  return (
    <div style={{ flex: 1, minHeight: 0 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.3}
        maxZoom={2}
        attributionPosition="bottom-right"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={28}
          size={1}
          color="rgba(31,30,27,.06)"
        />
        <Controls />

        {/* Graph legend */}
        <Legend />
      </ReactFlow>
    </div>
  );
}

function Legend() {
  return (
    <div
      style={{
        position: "absolute",
        left: 20,
        bottom: 20,
        display: "flex",
        gap: 14,
        padding: "10px 14px",
        background: "rgba(253,251,247,.85)",
        backdropFilter: "blur(12px)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        fontSize: 11.5,
        fontFamily: "var(--font-sans)",
        color: "var(--ink-muted)",
        alignItems: "center",
        zIndex: 5,
        flexWrap: "wrap",
        maxWidth: 700,
      }}
    >
      <LegendItem
        swatch={
          <span
            style={{
              width: 14,
              height: 14,
              borderRadius: 999,
              background: "var(--surface)",
              border: "1.5px solid var(--mastery-low)",
              position: "relative",
              display: "inline-block",
            }}
          >
            <span
              style={{
                position: "absolute",
                top: -2,
                right: -2,
                width: 5,
                height: 5,
                borderRadius: 999,
                background: "var(--mastery-low)",
              }}
            />
          </span>
        }
        label="struggle signal"
      />
      <LegendItem
        swatch={
          <span
            style={{
              width: 14,
              height: 14,
              borderRadius: 999,
              background: "var(--surface)",
              border: "1.5px solid var(--border-strong)",
              display: "inline-block",
            }}
          />
        }
        label="concept"
      />
      <LegendItem
        swatch={
          <span
            style={{
              width: 18,
              height: 12,
              borderRadius: 3,
              border: "1.5px dashed var(--accent)",
              background: "var(--surface)",
              display: "inline-block",
            }}
          />
        }
        label="flashcards"
      />
      <LegendItem
        swatch={
          <span
            style={{
              width: 18,
              height: 12,
              borderRadius: 3,
              background: "var(--accent)",
              display: "inline-block",
            }}
          />
        }
        label="quiz"
      />
      <span style={{ width: 1, alignSelf: "stretch", background: "var(--border)" }} />
      <LegendItem
        swatch={
          <svg width="22" height="6">
            <line x1="0" y1="3" x2="22" y2="3" stroke="var(--border-strong)" strokeWidth="2.4" />
          </svg>
        }
        label="contains"
      />
      <LegendItem
        swatch={
          <svg width="22" height="6">
            <line x1="0" y1="3" x2="20" y2="3" stroke="var(--ink-muted)" strokeWidth="1.4" />
            <path d="M 17 0 L 22 3 L 17 6 z" fill="var(--ink-muted)" />
          </svg>
        }
        label="prerequisite"
      />
      <LegendItem
        swatch={
          <svg width="22" height="6">
            <line
              x1="0"
              y1="3"
              x2="22"
              y2="3"
              stroke="var(--ink-muted)"
              strokeWidth="1"
              strokeDasharray="5 4"
            />
          </svg>
        }
        label="co-occurrence"
      />
      <LegendItem
        swatch={
          <svg width="22" height="6">
            <line
              x1="0"
              y1="3"
              x2="22"
              y2="3"
              stroke="var(--ink-muted)"
              strokeWidth="1"
              strokeDasharray="1 4"
            />
          </svg>
        }
        label="related"
      />
    </div>
  );
}

function LegendItem({
  swatch,
  label,
}: {
  swatch: React.ReactNode;
  label: string;
}) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
      {swatch}
      {label}
    </span>
  );
}
