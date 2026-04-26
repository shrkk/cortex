"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Eyebrow, Icon } from "./ui/primitives";
import type { Course } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/",        label: "Graph",      icon: "graph"   },
  { href: "/review",  label: "Flashcards", icon: "cards"   },
  { href: "/quiz",    label: "Quiz",       icon: "quiz"    },
  { href: "/library", label: "Sources",    icon: "library" },
];

export function Sidebar({ courses = [] }: { courses?: Course[] }) {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/" || pathname.startsWith("/courses");
    return pathname.startsWith(href);
  };

  return (
    <aside
      style={{
        width: 240,
        flexShrink: 0,
        borderRight: "1px solid var(--border)",
        background: "var(--paper)",
        padding: "20px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 24,
        height: "calc(100vh - 56px)",
        position: "sticky",
        top: 56,
        overflowY: "auto",
      }}
    >
      {/* Nav */}
      <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "7px 10px",
                borderRadius: 6,
                background: active ? "var(--surface-hover)" : "transparent",
                color: active ? "var(--ink-soft)" : "var(--ink-muted)",
                fontFamily: "var(--font-sans)",
                fontSize: 13.5,
                fontWeight: active ? 500 : 400,
                textDecoration: "none",
                transition: "background 200ms var(--ease)",
              }}
            >
              <Icon name={item.icon} size={16} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Courses */}
      {courses.length > 0 && (
        <div>
          <Eyebrow style={{ padding: "0 10px", marginBottom: 8 }}>Courses</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            {courses.map((c) => (
              <Link
                key={c.id}
                href={`/courses/${c.id}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "6px 10px",
                  borderRadius: 6,
                  color: "var(--ink)",
                  fontFamily: "var(--font-sans)",
                  fontSize: 13,
                  textDecoration: "none",
                  transition: "background 200ms var(--ease)",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "var(--surface-hover)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 999,
                    background:
                      (c.active_struggle_count ?? 0) > 0
                        ? "var(--mastery-low)"
                        : "var(--ink-faint)",
                    flexShrink: 0,
                  }}
                />
                <span style={{ flex: 1 }}>{c.title}</span>
                <span
                  style={{
                    fontSize: 11,
                    color: "var(--ink-faint)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {c.concept_count ?? 0}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Footer digest */}
      <div
        style={{
          marginTop: "auto",
          padding: "12px 10px",
          borderTop: "1px solid var(--border-soft)",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: 13,
            color: "var(--ink-soft)",
          }}
        >
          This week
        </div>
        <div
          style={{
            fontSize: 12,
            color: "var(--ink-muted)",
            marginTop: 4,
            lineHeight: 1.5,
          }}
        >
          Drop a source into the notch to start building your graph.
        </div>
      </div>
    </aside>
  );
}
