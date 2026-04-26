const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────

// FIX: was { name: string; concept_count?: number; struggle_count?: number }
// Backend CourseResponse uses "title"; concept_count and active_struggle_count
// are now returned by GET /courses via subquery aggregates (added in plan 06-01 Task 1 Step 0)
export interface Course {
  id: number;
  user_id: number;
  title: string;                    // was: name — backend CourseResponse.title
  description?: string;
  created_at: string;
  concept_count: number;            // was: missing — now returned by GET /courses
  active_struggle_count: number;    // was: struggle_count (wrong name) — now returned by GET /courses
}

export type SourceStatus = "pending" | "processing" | "done" | "error";
export type SourceType   = "pdf" | "url" | "image" | "text" | "chat_log";

// Source interface — add course_id (needed for library filtering)
export interface Source {
  id: number;
  course_id: number;     // needed for library filtering
  title?: string;
  source_type: SourceType;
  status: SourceStatus;
  created_at: string;
}

// FIX: was flat structure with node_type/label/has_struggle at root
// Backend GraphNode schema: { id, type, data: {...} }
export interface GraphNodeData {
  label: string;
  concept_id?: number;
  course_id?: number;
  quiz_id?: number;
  flashcard_id?: number;
  depth?: number;
  has_struggle_signals?: boolean;  // was: has_struggle
  flashcard_count?: number;
  source_count?: number;           // added to backend via task 1 (D-02 node sizing)
  question_count?: number;
  description?: string;
  front?: string;
  back?: string;
  card_type?: string;
}

export interface GraphNode {
  id: string;
  type: "course" | "concept" | "flashcard" | "quiz";  // was: node_type
  data: GraphNodeData;                                  // was: flat fields at root
}

// FIX: was { edge_type: "contains" | ... }
// Backend GraphEdge schema: { id, source, target, type, data }
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: "contains" | "co_occurrence" | "prerequisite" | "related";  // was: edge_type
  data?: { weight?: number };
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Concept interface — struggle_signals is dict | null (NOT array)
export interface Concept {
  id: number;
  title: string;
  summary?: string;
  key_points?: string[];
  gotchas?: string[];
  examples?: string[];
  student_questions?: string[];
  source_citations?: Array<{ source_id: number; title?: string; source_type: string }>;
  flashcard_count?: number;
  struggle_signals?: Record<string, unknown> | null;  // FIX: was Array<{label,detail}> — backend returns dict|null
  depth?: number;
}

export interface Flashcard {
  id: number;
  concept_id: number;
  front: string;
  back: string;
  card_type: "definition" | "application" | "gotcha" | "compare";
}

// FIX: was { id, question_type, prompt, topic, explanation }
// Backend question dict: { question_id, type, question, concept_id, options, correct_index, answered, grading }
export interface QuizQuestion {
  question_id: number;        // was: id
  type: "mcq" | "short_answer" | "application";  // was: question_type with "mcq"|"free"
  question: string;           // was: prompt
  concept_id: number;
  options?: string[];         // MCQ only
  correct_index?: number;     // MCQ only (never shown to student — present for reference)
  answered?: boolean;
  grading?: { correct: boolean; feedback: string } | null;
}

export interface Quiz {
  id: number;
  course_id: number;
  questions: QuizQuestion[];
}

// New: POST /quiz/{id}/answer response shape (backend/app/schemas/quiz.py AnswerResponse)
export interface AnswerResponse {
  grading: { correct: boolean; feedback: string };
  next_question: QuizQuestion | null;
  is_complete: boolean;
  score?: number;
  correct_count?: number;
  total?: number;
  concepts_to_review?: number[];
}
