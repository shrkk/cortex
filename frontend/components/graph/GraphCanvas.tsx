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
import { CourseNode, ConceptNode, QuizNode } from "./NodeTypes";
import type { GraphData, GraphNode } from "@/lib/api";

// nodeTypes MUST be defined outside the component body — prevents object recreation
const nodeTypes: NodeTypes = {
  course:   CourseNode,
  concept:  ConceptNode,
  quiz:     QuizNode,
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

// ── Radial layout ─────────────────────────────────────────────────────────────
// Size hints for centering — keep in sync with NodeTypes rendered sizes
function nodeSize(nodeType: string) {
  if (nodeType === "course") return { w: 130, h: 130 };
  if (nodeType === "quiz")   return { w: 140, h: 44  };
  return { w: 117, h: 117 }; // concept midpoint
}

// Deterministic pseudo-random — stable across re-renders
function seededRand(seed: number) {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x); // [0, 1)
}

function buildLayout(rawNodes: GraphNode[], rawEdges: GraphData["edges"]) {
  const courseNode   = rawNodes.find(n => n.type === "course");
  const conceptNodes = rawNodes.filter(n => n.type === "concept");
  const leafNodes    = rawNodes.filter(n => n.type === "quiz");

  // Map each leaf to its parent concept
  const parentOfLeaf: Record<string, string> = {};
  rawEdges.forEach(e => {
    const tgt = rawNodes.find(n => n.id === e.target);
    if (tgt?.type === "quiz") {
      parentOfLeaf[e.target] = e.source;
    }
  });

  const CENTER = { x: 0, y: 0 };
  const n = conceptNodes.length || 1;
  // 170px arc per concept ensures adequate spacing between 120px circles
  const CONCEPT_RADIUS = Math.max(300, (n * 140) / (2 * Math.PI));
  const LEAF_OFFSET    = 130;

  const positions: Record<string, { x: number; y: number }> = {};

  if (courseNode) positions[courseNode.id] = { ...CENTER };

  conceptNodes.forEach((node, i) => {
    // Angular positions are uniformly spaced (no angular jitter) to prevent overlap.
    // Only radius varies ±14% for an organic feel.
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    const r     = CONCEPT_RADIUS * (0.93 + seededRand(i) * 0.14); // 93%–107%
    positions[node.id] = {
      x: CENTER.x + r * Math.cos(angle),
      y: CENTER.y + r * Math.sin(angle),
    };
  });

  // Group leaves by parent, fan outward from concept
  const leavesByParent: Record<string, typeof leafNodes> = {};
  leafNodes.forEach(leaf => {
    const pid = parentOfLeaf[leaf.id];
    if (!pid) return;
    (leavesByParent[pid] ??= []).push(leaf);
  });

  Object.entries(leavesByParent).forEach(([parentId, leaves]) => {
    const pp = positions[parentId];
    if (!pp) return;
    const outAngle = Math.atan2(pp.y - CENTER.y, pp.x - CENTER.x);
    const spread = 0.45;
    leaves.forEach((leaf, i) => {
      const offset = (i - (leaves.length - 1) / 2) * spread;
      const a = outAngle + offset;
      positions[leaf.id] = {
        x: pp.x + LEAF_OFFSET * Math.cos(a),
        y: pp.y + LEAF_OFFSET * Math.sin(a),
      };
    });
  });

  // Fallback for disconnected nodes
  rawNodes.forEach((node, i) => {
    if (!positions[node.id]) {
      positions[node.id] = { x: CONCEPT_RADIUS * 2 + i * 110, y: 0 };
    }
  });

  const nodes: Node[] = rawNodes.map((n) => {
    const pos = positions[n.id];
    const { w, h } = nodeSize(n.type);
    return {
      id: n.id,
      type: n.type,
      position: { x: pos.x - w / 2, y: pos.y - h / 2 },
      data: {
        label:           n.data.label,
        source_count:    n.data.source_count,
        has_struggle:    n.data.has_struggle_signals,
        flashcard_count: n.data.flashcard_count,
        concept_id:      n.data.concept_id,
        quiz_id:         n.data.quiz_id,
        course_id:       n.data.course_id,
      },
    };
  });

  // Strip co-occurrence edges — too noisy visually
  const edges: Edge[] = rawEdges
    .filter(e => e.type !== "co_occurrence")
    .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "cortex",
      data: { edge_type: e.type },
    }));

  return { nodes, edges };
}

// ── Component ─────────────────────────────────────────────────────────────────
export function GraphCanvas({
  graphData,
  onNodeClick,
}: {
  graphData: GraphData | null | undefined;
  onNodeClick?: (nodeId: string, nodeType: string, nodeData?: Record<string, unknown>) => void;
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
      onNodeClick?.(node.id, node.type ?? "concept", node.data as Record<string, unknown>);
    },
    [onNodeClick]
  );

  return (
    <div style={{ width: "100%", height: "100%" }}>
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
          color="rgba(31,30,27,0.06)"
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
