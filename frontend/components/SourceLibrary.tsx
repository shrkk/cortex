"use client";

import React, { useRef, useState } from "react";
import type { Source, Course, SourceStatus } from "@/lib/api";

// Status badge styles — exact colors from UI-SPEC §Status Badge Labels
const STATUS_BADGE_STYLE: Record<SourceStatus, { bg: string; color: string; label: string }> = {
  pending:    { bg: "rgba(154,147,136,0.15)", color: "#9A9388",  label: "Pending"    },
  processing: { bg: "rgba(193,138,63,0.15)",  color: "#C18A3F",  label: "Processing" },
  done:       { bg: "rgba(107,142,90,0.15)",  color: "#6B8E5A",  label: "Done"       },
  error:      { bg: "rgba(181,96,74,0.15)",   color: "#B5604A",  label: "Error"      },
};

const TYPE_ABBR: Record<string, string> = {
  pdf:      "PDF",
  url:      "URL",
  image:    "IMG",
  text:     "TXT",
  chat_log: "CHAT",
};

const KIND_OPTIONS = [
  { value: "pdf",   label: "PDF" },
  { value: "image", label: "Image" },
  { value: "text",  label: "Text" },
];

interface SourceLibraryProps {
  sources: Source[];
  courses: Course[];
  onUpload?: (file: File, courseId: number, kind: string) => Promise<void>;
}

export function SourceLibrary({ sources, courses, onUpload }: SourceLibraryProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(
    courses.length > 0 ? courses[0].id : null
  );
  const [kind, setKind] = useState<string>("pdf");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Update selectedCourseId when courses load (if not yet set)
  React.useEffect(() => {
    if (selectedCourseId === null && courses.length > 0) {
      setSelectedCourseId(courses[0].id);
    }
  }, [courses, selectedCourseId]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!selectedCourseId) {
      setUploadError("Please select a course first.");
      return;
    }
    setUploadError(null);
    setUploading(true);
    try {
      await onUpload?.(file, selectedCourseId, kind);
    } catch {
      setUploadError("Upload failed. Check file type and try again.");
    } finally {
      setUploading(false);
      // Reset file input so same file can be re-uploaded
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const UploaderCard = (
    <div style={{
      marginTop: 32,
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      padding: 24,
    }}>
      {/* Uploader label — exact copy per UI-SPEC */}
      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--ink-muted)", marginBottom: 16, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        Fallback uploader — prefer dropping into the notch
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Course selector */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: "var(--ink-muted)" }}>
            Course
          </label>
          {courses.length === 0 ? (
            <div style={{ fontSize: 13, color: "var(--ink-muted)", fontStyle: "italic" }}>
              No courses yet — create a course first.
            </div>
          ) : (
            <select
              value={selectedCourseId ?? ""}
              onChange={(e) => setSelectedCourseId(Number(e.target.value))}
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 6,
                color: "var(--ink)",
                padding: "7px 10px",
                fontFamily: "var(--font-sans)",
                fontSize: 13,
                cursor: "pointer",
                outline: "none",
              }}
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
          )}
        </div>

        {/* Kind selector */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ fontSize: 12, fontWeight: 500, color: "var(--ink-muted)" }}>
            File type
          </label>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              color: "var(--ink)",
              padding: "7px 10px",
              fontFamily: "var(--font-sans)",
              fontSize: 13,
              cursor: "pointer",
              outline: "none",
            }}
          >
            {KIND_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* File input + button */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.txt,.md"
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading || courses.length === 0}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              background: "var(--accent)",
              color: "var(--accent-ink)",
              border: "none",
              borderRadius: 6,
              padding: "8px 16px",
              fontFamily: "var(--font-sans)",
              fontSize: 13.5,
              fontWeight: 500,
              cursor: (uploading || courses.length === 0) ? "not-allowed" : "pointer",
              opacity: (uploading || courses.length === 0) ? 0.5 : 1,
              transition: "opacity 200ms var(--ease)",
            }}
          >
            {uploading ? "Uploading…" : "Upload File"}
          </button>
          {uploadError && (
            <span style={{ fontSize: 12, color: "#B5604A" }}>{uploadError}</span>
          )}
        </div>

        <div style={{ fontSize: 11, color: "var(--ink-faint)", lineHeight: 1.4 }}>
          This will create a new source. Duplicates are detected automatically.
        </div>
      </div>
    </div>
  );

  // Empty state — show when no sources, but still render uploader below
  if (!sources.length) {
    return (
      <div style={{ flex: 1, padding: "32px 48px", overflowY: "auto" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          {/* Header */}
          <div style={{ marginBottom: 28 }}>
            <h1 style={{
              fontFamily: "var(--font-serif)",
              fontSize: 32,
              fontWeight: 500,
              color: "var(--ink-soft)",
              letterSpacing: "-0.01em",
              margin: 0,
            }}>
              Sources
            </h1>
          </div>

          {/* Empty state — exact copy from UI-SPEC §Empty States */}
          <div style={{
            textAlign: "center",
            padding: "48px 16px",
            color: "var(--ink-muted)",
          }}>
            <p style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)", marginBottom: 6, margin: "0 0 6px 0" }}>
              No sources yet
            </p>
            <p style={{ fontSize: 14, margin: 0 }}>
              Prefer dropping into the notch. Or use the uploader below as a fallback.
            </p>
          </div>

          {UploaderCard}
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, padding: "32px 48px", overflowY: "auto" }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <h1 style={{
            fontFamily: "var(--font-serif)",
            fontSize: 32,
            fontWeight: 500,
            color: "var(--ink-soft)",
            letterSpacing: "-0.01em",
            margin: 0,
          }}>
            Sources
          </h1>
          <div style={{ color: "var(--ink-muted)", fontSize: 13.5, marginTop: 6 }}>
            {sources.length} source{sources.length !== 1 ? "s" : ""} · prefer dropping into the notch
          </div>
        </div>

        {/* Source table */}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-sans)", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Title", "Type", "Course", "Status", "Uploaded"].map((col) => (
                  <th key={col} style={{
                    textAlign: "left",
                    padding: "8px 12px",
                    fontSize: 11,
                    fontWeight: 500,
                    color: "var(--ink-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => {
                const badge = STATUS_BADGE_STYLE[s.status] ?? STATUS_BADGE_STYLE.pending;
                const abbr = TYPE_ABBR[s.source_type] ?? "FILE";
                // Find course name if available
                const course = courses.find((c) => c.id === s.course_id);
                return (
                  <tr
                    key={s.id}
                    style={{
                      borderBottom: "1px solid var(--border-soft)",
                      transition: "background 200ms var(--ease)",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    {/* Title */}
                    <td style={{ padding: "12px 12px", color: "var(--ink-soft)", fontWeight: 500 }}>
                      {s.title ?? `Source ${s.id}`}
                    </td>

                    {/* Type badge — font-mono per UI-SPEC */}
                    <td style={{ padding: "12px 12px" }}>
                      <span style={{
                        fontSize: 11,
                        fontWeight: 600,
                        fontFamily: "var(--font-mono)",
                        padding: "1px 6px",
                        borderRadius: "var(--radius-xs, 3px)",
                        background: "var(--surface)",
                        border: "1px solid var(--border)",
                        color: "var(--ink-muted)",
                        textTransform: "uppercase",
                      }}>
                        {abbr}
                      </span>
                    </td>

                    {/* Course */}
                    <td style={{ padding: "12px 12px", color: "var(--ink-muted)" }}>
                      {course?.title ?? `Course ${s.course_id}`}
                    </td>

                    {/* Status badge — exact colors from UI-SPEC */}
                    <td style={{ padding: "12px 12px" }}>
                      <span style={{
                        fontSize: 11,
                        fontWeight: 600,
                        padding: "2px 8px",
                        borderRadius: "var(--radius-pill, 999px)",
                        background: badge.bg,
                        color: badge.color,
                        letterSpacing: "0.03em",
                      }}>
                        {badge.label}
                      </span>
                    </td>

                    {/* Uploaded (relative time) */}
                    <td style={{ padding: "12px 12px", color: "var(--ink-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                      {formatRelativeTime(s.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {UploaderCard}
      </div>
    </div>
  );
}

/** Format a date string as a relative time label (e.g. "2 days ago") */
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}
