"use client";

import useSWR, { useSWRConfig } from "swr";
import { AppShell } from "@/components/AppShell";
import { SourceLibrary } from "@/components/SourceLibrary";
import { apiFetch, type Source, type Course } from "@/lib/api";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LibraryPage() {
  const { data: sources = [] } = useSWR<Source[]>("/sources", (url: string) => apiFetch<Source[]>(url));
  const { data: courses = [] } = useSWR<Course[]>("/courses", (url: string) => apiFetch<Course[]>(url));
  const { mutate } = useSWRConfig();

  // GET /sources SWR — fetches source list for the library table
  // GET /courses SWR — populates course selector dropdown in the upload form

  const handleUpload = async (file: File, courseId: number, kind: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("course_id", String(courseId));
    form.append("kind", kind);
    // Do NOT set Content-Type header — browser sets it with boundary for multipart
    await fetch(`${BASE}/ingest`, { method: "POST", body: form });
    mutate("/sources");
  };

  return (
    <AppShell courses={courses}>
      <SourceLibrary
        sources={sources}
        courses={courses}
        onUpload={handleUpload}
      />
    </AppShell>
  );
}
