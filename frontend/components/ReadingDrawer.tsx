"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { Button, Card, Eyebrow, Icon, Pill } from "./ui/primitives";
import { FlashcardView } from "./FlashcardView";
import { apiFetch, type Concept, type Flashcard } from "@/lib/api";

// ── Math rendering (used for concept fields, not chat) ────────────────────────
function renderMath(text: string): string {
  return text
    .replace(/\$\$([^$]+)\$\$/g, (_, expr) => {
      try { return katex.renderToString(expr.trim(), { displayMode: true, throwOnError: false }); }
      catch { return _; }
    })
    .replace(/\$([^$\n]+)\$/g, (_, expr) => {
      try { return katex.renderToString(expr.trim(), { displayMode: false, throwOnError: false }); }
      catch { return _; }
    });
}

function MathText({ text, serif = false, style }: { text: string; serif?: boolean; style?: React.CSSProperties }) {
  return (
    <span
      style={{ fontFamily: serif ? "var(--font-serif)" : undefined, ...style }}
      dangerouslySetInnerHTML={{ __html: renderMath(text) }}
    />
  );
}

// ── Markdown renderer for chat responses ─────────────────────────────────────
function ChatMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        code({ node, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || "");
          const inline = !match && !String(children).includes("\n");
          if (inline) {
            return (
              <code style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12.5,
                background: "var(--paper)",
                border: "1px solid var(--border)",
                borderRadius: 4,
                padding: "1px 5px",
                color: "var(--ink-soft)",
              }} {...props}>
                {children}
              </code>
            );
          }
          return (
            <SyntaxHighlighter
              style={oneDark}
              language={match ? match[1] : "text"}
              PreTag="div"
              customStyle={{
                borderRadius: 8,
                fontSize: 12.5,
                margin: "8px 0",
                padding: "12px 14px",
              }}
            >
              {String(children).replace(/\n$/, "")}
            </SyntaxHighlighter>
          );
        },
        p({ children }) {
          return <p style={{ margin: "0 0 8px", lineHeight: 1.65 }}>{children}</p>;
        },
        ul({ children }) {
          return <ul style={{ margin: "4px 0 8px", paddingLeft: 20 }}>{children}</ul>;
        },
        ol({ children }) {
          return <ol style={{ margin: "4px 0 8px", paddingLeft: 20 }}>{children}</ol>;
        },
        li({ children }) {
          return <li style={{ marginBottom: 4, lineHeight: 1.6 }}>{children}</li>;
        },
        strong({ children }) {
          return <strong style={{ fontWeight: 600, color: "var(--ink)" }}>{children}</strong>;
        },
        blockquote({ children }) {
          return (
            <blockquote style={{
              borderLeft: "3px solid var(--border-strong)",
              paddingLeft: 12,
              margin: "8px 0",
              color: "var(--ink-muted)",
              fontStyle: "italic",
            }}>
              {children}
            </blockquote>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

// ── Suggested questions (seeded from concept content) ────────────────────────
function seedQuestions(concept: Concept): string[] {
  const base = [
    `What is the key intuition behind ${concept.title}?`,
    `What are the most common mistakes students make with ${concept.title}?`,
  ];
  if (concept.examples && concept.examples.length > 0) {
    base.push(`Can you walk me through an example of ${concept.title}?`);
  } else if (concept.gotchas && concept.gotchas.length > 0) {
    base.push(`Why is ${concept.title} often misunderstood?`);
  }
  return base.slice(0, 3);
}

// ── Chat panel ────────────────────────────────────────────────────────────────
type ChatMsg = { role: "user" | "assistant"; content: string };

function ChatPanel({ concept }: { concept: Concept }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const suggestions = seedQuestions(concept);

  const send = useCallback(async (question: string) => {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${BASE}/concepts/${concept.id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok || !res.body) throw new Error("Request failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = "";
      setMessages(prev => [...prev, { role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        acc += decoder.decode(value, { stream: true });
        setMessages(prev => {
          const next = [...prev];
          next[next.length - 1] = { role: "assistant", content: acc };
          return next;
        });
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Something went wrong. Try again." }]);
    } finally {
      setLoading(false);
    }
  }, [concept.id, loading]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <Eyebrow style={{ marginBottom: 12 }}>Ask Cortex</Eyebrow>

      {/* Suggested questions */}
      {messages.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 16 }}>
          {suggestions.map((q, i) => (
            <button
              key={i}
              onClick={() => send(q)}
              style={{
                textAlign: "left",
                padding: "9px 14px",
                borderRadius: 8,
                border: "1px solid var(--border)",
                background: "var(--paper)",
                color: "var(--ink-soft)",
                fontFamily: "var(--font-serif)",
                fontSize: 13.5,
                lineHeight: 1.4,
                cursor: "pointer",
                transition: "border-color 150ms, background 150ms",
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.borderColor = "var(--border-strong)";
                (e.currentTarget as HTMLElement).style.background = "var(--surface-hover)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                (e.currentTarget as HTMLElement).style.background = "var(--paper)";
              }}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Message thread */}
      {messages.length > 0 && (
        <div style={{
          display: "flex", flexDirection: "column", gap: 12,
          maxHeight: 340, overflowY: "auto", marginBottom: 12,
          paddingRight: 4,
        }}>
          {messages.map((m, i) => (
            <div key={i} style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "88%",
            }}>
              {m.role === "user" ? (
                <div style={{
                  background: "var(--ink-soft)",
                  color: "var(--paper)",
                  padding: "8px 14px",
                  borderRadius: "12px 12px 4px 12px",
                  fontFamily: "var(--font-sans)",
                  fontSize: 13.5,
                  lineHeight: 1.45,
                }}>
                  {m.content}
                </div>
              ) : (
                <div style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  padding: "10px 14px",
                  borderRadius: "12px 12px 12px 4px",
                  fontFamily: "var(--font-serif)",
                  fontSize: 14,
                  lineHeight: 1.6,
                  color: "var(--ink)",
                }}>
                  {m.content
                    ? <ChatMarkdown content={m.content} />
                    : <span style={{ color: "var(--ink-faint)", fontStyle: "italic" }}>Thinking…</span>}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Input */}
      <div style={{
        display: "flex", gap: 8, alignItems: "flex-end",
        borderTop: messages.length > 0 ? "1px solid var(--border-soft)" : undefined,
        paddingTop: messages.length > 0 ? 12 : 0,
      }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
          placeholder="Ask a question about this concept…"
          rows={2}
          style={{
            flex: 1, resize: "none",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "8px 12px",
            fontFamily: "var(--font-sans)",
            fontSize: 13.5,
            color: "var(--ink)",
            background: "var(--paper)",
            outline: "none",
            lineHeight: 1.45,
          }}
          onFocus={e => (e.target.style.borderColor = "var(--border-strong)")}
          onBlur={e => (e.target.style.borderColor = "var(--border)")}
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim() || loading}
          style={{
            width: 36, height: 36, borderRadius: 8, border: 0,
            background: input.trim() && !loading ? "var(--ink-soft)" : "var(--border)",
            color: input.trim() && !loading ? "var(--paper)" : "var(--ink-faint)",
            cursor: input.trim() && !loading ? "pointer" : "default",
            display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0, transition: "background 150ms",
          }}
        >
          <Icon name="arrowRight" size={16} />
        </button>
      </div>
    </div>
  );
}

// ── ReadingDrawer ─────────────────────────────────────────────────────────────
interface ReadingDrawerProps {
  concept: Concept | null;
  flashcards?: Flashcard[];
  onClose: () => void;
  onGenerateQuiz?: () => void;
  onStruggleToggled?: () => void;
}

export function ReadingDrawer({
  concept,
  flashcards = [],
  onClose,
  onGenerateQuiz,
  onStruggleToggled,
}: ReadingDrawerProps) {
  const [mode, setMode] = useState<"detail" | "flashcards">("detail");
  const [localStruggle, setLocalStruggle] = useState<boolean>(false);
  const [togglingStruggle, setTogglingStruggle] = useState(false);

  useEffect(() => {
    if (concept) {
      setMode("detail");
      setLocalStruggle(
        concept.struggle_signals != null && Object.keys(concept.struggle_signals).length > 0
      );
    }
  }, [concept?.id]);

  const toggleStruggle = async () => {
    if (!concept || togglingStruggle) return;
    setTogglingStruggle(true);
    const wasFlagged = localStruggle;
    try {
      const res = await apiFetch<{ struggle_signals: Record<string, unknown> | null }>(
        `/concepts/${concept.id}/mark-struggle`,
        { method: "POST" }
      );
      const nowFlagged = res.struggle_signals != null && Object.keys(res.struggle_signals).length > 0;
      setLocalStruggle(nowFlagged);
      onStruggleToggled?.();
      // Auto-generate a quiz when a concept is newly flagged as trouble
      if (!wasFlagged && nowFlagged && concept.course_id) {
        apiFetch("/quiz", {
          method: "POST",
          body: JSON.stringify({ course_id: concept.course_id, num_questions: 7 }),
        }).catch(() => {}); // fire-and-forget — failure is silent
      }
    } finally {
      setTogglingStruggle(false);
    }
  };

  if (!concept) return null;

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, background: "var(--backdrop)",
        zIndex: 50, animation: "fadeIn 200ms var(--ease)",
      }} />

      <aside style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: 560,
        background: "var(--surface)", borderLeft: "1px solid var(--border)",
        boxShadow: "var(--shadow-md)", zIndex: 51,
        overflowY: mode === "flashcards" ? "hidden" : "auto",
        display: "flex", flexDirection: "column",
        animation: "slideInRight 300ms var(--ease)",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "14px 20px", borderBottom: "1px solid var(--border)",
          position: "sticky", top: 0, background: "var(--surface)", zIndex: 1,
        }}>
          {mode === "flashcards" ? (
            <button onClick={() => setMode("detail")} style={{
              display: "flex", alignItems: "center", gap: 6, border: 0,
              background: "transparent", color: "var(--ink-muted)",
              fontFamily: "var(--font-sans)", fontSize: 13, cursor: "pointer", padding: "4px 0",
            }}>
              <Icon name="arrowLeft" size={14} /> Back
            </button>
          ) : (
            <Pill tone={localStruggle ? "low" : "neutral"} dot>
              {localStruggle ? "Trouble node" : "Concept"}
            </Pill>
          )}
          <div style={{ flex: 1 }} />

          {/* Mark as trouble toggle */}
          {mode === "detail" && (
            <button
              onClick={toggleStruggle}
              disabled={togglingStruggle}
              title={localStruggle ? "Remove trouble flag" : "Mark as trouble node"}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "5px 10px", borderRadius: 6,
                border: `1px solid ${localStruggle ? "var(--mastery-low)" : "var(--border)"}`,
                background: localStruggle ? "var(--mastery-low-soft)" : "transparent",
                color: localStruggle ? "var(--mastery-low)" : "var(--ink-muted)",
                fontFamily: "var(--font-sans)", fontSize: 12.5, fontWeight: 500,
                cursor: "pointer", transition: "all 150ms",
              }}
            >
              <Icon name="flag" size={13} />
              {localStruggle ? "Flagged" : "Flag as trouble"}
            </button>
          )}

          <button onClick={onClose} style={{
            width: 28, height: 28, borderRadius: 6, border: 0,
            background: "transparent", display: "flex", alignItems: "center",
            justifyContent: "center", color: "var(--ink-muted)", cursor: "pointer",
          }}>
            <Icon name="close" size={16} />
          </button>
        </div>

        {/* Body */}
        {mode === "flashcards" ? (
          <FlashcardView flashcards={flashcards} conceptTitle={concept.title} />
        ) : (
          <ConceptDetail
            concept={concept}
            localStruggle={localStruggle}
            flashcardCount={flashcards.length}
            onViewFlashcards={() => setMode("flashcards")}
            onGenerateQuiz={onGenerateQuiz}
          />
        )}
      </aside>
    </>
  );
}

// ── ConceptDetail ─────────────────────────────────────────────────────────────
function ConceptDetail({
  concept,
  localStruggle,
  flashcardCount,
  onViewFlashcards,
  onGenerateQuiz,
}: {
  concept: Concept;
  localStruggle: boolean;
  flashcardCount: number;
  onViewFlashcards: () => void;
  onGenerateQuiz?: () => void;
}) {
  return (
    <div style={{ padding: "28px 28px 48px", display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Title */}
      <div>
        <Eyebrow style={{ marginBottom: 6 }}>Concept</Eyebrow>
        <h1 style={{
          fontFamily: "var(--font-serif)", fontSize: 30, color: "var(--ink-soft)",
          fontWeight: 500, letterSpacing: "-0.01em", margin: 0, lineHeight: 1.2,
        }}>
          {concept.title}
        </h1>
        <div style={{ color: "var(--ink-muted)", fontSize: 12.5, marginTop: 10 }}>
          {concept.flashcard_count ?? 0} flashcards
        </div>
      </div>

      {/* Definition */}
      {concept.summary && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Definition</Eyebrow>
          <p style={{
            fontFamily: "var(--font-serif)", fontSize: 15.5, lineHeight: 1.7,
            color: "var(--ink)", maxWidth: "60ch",
          }}>
            <MathText text={concept.summary} />
          </p>
        </div>
      )}

      {/* Gotchas */}
      {concept.gotchas && concept.gotchas.length > 0 && (
        <div style={{
          background: "var(--highlight-bg)", borderLeft: "3px solid var(--highlight-bar)",
          borderRadius: 6, padding: "14px 18px",
        }}>
          <Eyebrow style={{ color: "#7A5524", marginBottom: 8 }}>Gotchas</Eyebrow>
          <ul style={{ margin: 0, paddingLeft: 18, listStyleType: "disc" }}>
            {concept.gotchas.map((g, i) => (
              <li key={i} style={{ marginBottom: i < concept.gotchas!.length - 1 ? 6 : 0 }}>
                <MathText text={g} serif style={{
                  fontFamily: "var(--font-serif)", fontSize: 14.5,
                  lineHeight: 1.6, color: "var(--ink-soft)",
                }} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Key points */}
      {concept.key_points && concept.key_points.length > 0 && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Key points</Eyebrow>
          <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
            {concept.key_points.map((p, i) => (
              <li key={i}>
                <MathText text={p} serif style={{
                  fontFamily: "var(--font-serif)", fontSize: 14.5,
                  lineHeight: 1.65, color: "var(--ink)",
                }} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Examples */}
      {concept.examples && concept.examples.length > 0 && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Examples</Eyebrow>
          <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
            {concept.examples.map((ex, i) => (
              <li key={i}>
                <MathText text={ex} serif style={{
                  fontFamily: "var(--font-serif)", fontSize: 14.5,
                  lineHeight: 1.65, color: "var(--ink)",
                }} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Student questions */}
      {concept.student_questions && concept.student_questions.length > 0 && (
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Student questions</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {concept.student_questions.map((q, i) => (
              <div key={i} style={{
                fontFamily: "var(--font-serif)", fontStyle: "italic",
                color: "var(--ink-soft)", fontSize: 14, lineHeight: 1.55,
                paddingLeft: 12, borderLeft: "2px solid var(--border)",
              }}>
                {q}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sources */}
      {concept.source_citations && concept.source_citations.length > 0 && (
        <div>
          <Eyebrow style={{ marginBottom: 10 }}>Sources</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {concept.source_citations.map((s, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 12, padding: "10px 0",
                borderTop: i > 0 ? "1px solid var(--border-soft)" : undefined,
              }}>
                <div style={{
                  width: 28, height: 34, border: "1px solid var(--border)", borderRadius: 3,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "var(--font-mono)", fontSize: 8.5,
                  color: "var(--ink-muted)", background: "var(--paper)", flexShrink: 0,
                }}>
                  {s.source_type}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: "var(--font-serif)", fontSize: 14, color: "var(--ink-soft)", fontWeight: 500 }}>
                    {s.title ?? `Source ${s.source_id}`}
                  </div>
                </div>
                <Icon name="arrowRight" size={14} color="var(--ink-faint)" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 8 }}>
        {localStruggle && flashcardCount > 0 && (
          <Button icon="cards" onClick={onViewFlashcards}>
            Flashcards ({flashcardCount})
          </Button>
        )}
        <Button variant="secondary" onClick={onGenerateQuiz}>Generate quiz</Button>
      </div>

      {/* Divider */}
      <div style={{ borderTop: "1px solid var(--border)", margin: "0 -4px" }} />

      {/* Chat panel */}
      <ChatPanel concept={concept} />
    </div>
  );
}
