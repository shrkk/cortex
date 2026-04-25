# Feature Landscape: Student Second-Brain / Knowledge Graph / SRS

**Domain:** Student second-brain with knowledge graph + spaced-repetition
**Project:** Cortex (hackathon scope, locked feature set)
**Researched:** 2026-04-25
**Confidence:** HIGH for mature competitor patterns (Anki, Obsidian, Roam, Remnote, Readwise, Logseq — all extensively documented in training data through 2025). LOW for any live-scraped data (tools unavailable).

---

## Purpose of This Document

This research does NOT expand Cortex's feature set. The stack and features are locked (see PROJECT.md → Active Requirements). The goals are:

1. Validate which spec features are **table stakes** vs **differentiators**
2. Identify which are **demo-critical** vs **nice-to-have**
3. Surface any **obvious missing table-stakes** the spec may have overlooked
4. Note **competitor implementation quality signals** that inform how Cortex should build what it's already committed to

---

## Competitor Reference Map

| Product | Core Loop | What Students Love | What Students Hate |
|---------|-----------|-------------------|-------------------|
| **Anki** | Manual card creation → SM-2 review | Proven algorithm, flexibility, free | Creating cards is brutal work; no auto-import |
| **Remnote** | Notes → auto-generated cards (::) | Tight note-to-card coupling, hierarchical concepts | Complex UX, slow on large vaults |
| **Readwise** | Highlights → SRS review | Zero-friction ingestion (already reading) | Cards disconnected from a concept graph; no "why does this matter" context |
| **Obsidian** | Notes → graph view | Local-first, plugin ecosystem, bidirectional links | Graph view is visually impressive but cognitively useless — nodes are filenames, not concepts |
| **Roam** | Outlines → backlinks → graph | Daily notes rhythm, block references | Steep learning curve; graph view suffers same problem as Obsidian |
| **Logseq** | Outlines → graph | Open source, Roam-like | Graph view: same problem; flashcard plugin is bolted-on |
| **Notion** | Flexible docs | Familiarity | No SRS, no graph; students use it as a filing cabinet not a study tool |

**The gap Cortex fills:** Every competitor either automates ingestion OR builds a knowledge graph OR does SRS. None does all three with zero manual effort between "I have a PDF" and "I'm studying."

---

## Table Stakes

Features users expect from this category. Missing = product feels broken or incomplete.

| Feature | Why Expected | Complexity | Cortex Spec Has It? | Notes |
|---------|--------------|------------|---------------------|-------|
| **Card front / back reveal** | Anki established this as the universal review UX; anything else feels alien | Low | YES (Study page) | The "show front → tap → reveal back" pattern is non-negotiable |
| **Grade buttons after reveal** | SM-2 or any SRS requires grading; "Again/Hard/Good/Easy" is the Anki standard that users have muscle memory for | Low | YES (grades 1/3/4/5) | Label mapping matters: spec uses 1/3/4/5 internally; UI should show "Again / Hard / Good / Easy" not numbers |
| **Cards due today count** | Students orient their study session by "how many cards do I have today?"; missing this = anxiety | Low | YES (Dashboard: "cards due today") | Must be visible before entering a session, not after |
| **Progress indicator during session** | "Card 7 of 23" or a progress bar; without it sessions feel infinite | Low | YES (Study page: progress bar) | — |
| **Card review completes cleanly** | When due=0, session ends with a clear "you're done" state, not an empty screen | Low | Implied but not explicit | RISK: spec doesn't explicitly define the empty-queue state. Should show: 0 due + next due date/time |
| **Course / deck organization** | Students compartmentalize by subject; mixing CS229 and BIO101 cards = useless | Low | YES (course-scoped everything) | — |
| **Knowledge graph node coloring by mastery** | Once a mastery signal exists, students expect a visual heat map — they navigate toward red nodes | Low-Med | YES (red/yellow/green by mastery) | — |
| **Node detail panel** | Clicking a graph node must show what the concept is, not just its name; without this the graph is decoration | Med | YES (Node detail panel spec'd) | The spec's detail panel is comprehensive — this is executed well |
| **Source attribution / citations** | Students need to know WHERE a concept came from to go back and study the source material | Med | YES (source citations in node panel) | — |
| **"What should I study?" entry point** | The dashboard/graph must answer "what do I do now?" at a glance, or students default to Anki anyway | Low | YES (weak concepts in Dashboard, graph coloring) | — |
| **Error/status feedback on ingestion** | If a drop silently fails, students lose trust immediately | Low | YES (Cortex status pill per drop) | — |
| **Fallback when system is off** | macOS notch taking over drag target with no escape is a show-stopper | Low | YES (fallback to NotchDrop behavior when disabled) | — |

---

## Differentiators

Features that give Cortex a competitive edge. Students don't expect these, but they create the "wow" moment.

| Feature | Value Proposition | Complexity | Cortex Spec Has It? | Demo-Critical? | Notes |
|---------|-------------------|------------|---------------------|----------------|-------|
| **Zero-friction ingestion via notch drop** | Every competitor requires copy-paste, upload UIs, or manual highlight export. Drag-into-notch is the fastest known path from "I have a PDF" to "studying it" | High (fork of NotchDrop) | YES (Cortex Drop) | YES — this IS the demo opener | No competitor does this; Readwise is closest (browser extension) but still requires manual highlight |
| **Auto-generated concept graph from ingested content** | Obsidian/Roam graphs show files; Cortex graph shows extracted concepts with prerequisite/related edges. Completely different cognitive utility | High (LLM extraction pipeline) | YES (Knowledge graph) | YES | The course → concept → prerequisite depth hierarchy is genuinely novel vs competitors |
| **One-click "weak spots" quiz** | Most SRS tools make you navigate to weak areas manually. A button that instantly generates a quiz targeting your bottom-quartile mastery is rare | Med (quiz endpoint + mastery signal) | YES (`weak_spots` scope) | YES — this is the "killer button" | RemNote has something similar but it's buried; no competitor surfaces it this cleanly |
| **Auto-generated flashcards from concepts** | Anki's primary pain point is card creation. Cortex eliminates it entirely via LLM generation (definition/application/gotcha/compare) | High (LLM generation) | YES (3–6 cards per concept) | YES | Card quality will be the credibility test at demo |
| **Struggle signals as visible graph state** | "Pulsing dot" on nodes with struggle flags is a visual affordance no competitor has; turns abstract SRS scores into a navigable map | Med (5 signal types + UI) | YES (pulsing dot on struggle nodes) | YES — uniquely visual | This is demo gold: graph with pulsing red nodes is immediately understood without explanation |
| **Mixed card types per concept** | Anki cards are whatever the user writes. Cortex auto-generates definition + application + gotcha + compare — learning science supports mixed-type practice | Med | YES (4 types in spec) | MEDIUM | Not visible in demo but improves card quality perception |
| **Gotchas surfaced in node panel** | "Here's what students get wrong about this concept" is a study insight most tools don't provide | Med (LLM extraction) | YES (amber gotchas in node panel) | YES | Makes the node panel feel like a tutor, not a filing cabinet |
| **Content deduplication** | Dropping the same PDF twice shouldn't create duplicate concepts; students don't think about this but notice when it's broken | Med | YES (content_hash) | LOW for demo | Table stakes for production, deduplication is hygiene not feature |
| **Clipboard-native ingestion** | ⌘V while notch active captures images, URLs, text — covers students who screenshot lecture slides | Low-Med | YES | MEDIUM | Secondary to drag but expands ingestion surface area |

---

## Anti-Features

Things the spec has deliberately excluded, validated by competitor evidence.

| Anti-Feature | Why Avoid | Competitor Evidence | Spec Status |
|--------------|-----------|---------------------|-------------|
| **Manual card creation** | Anki's biggest UX debt. If Cortex adds manual card creation at hackathon scope, it dilutes the "zero effort" core value and is never polished enough to compete with Anki anyway | Anki has had 15 years to polish manual creation; Cortex should own auto-generation entirely | OUT OF SCOPE (not mentioned in spec — correct) |
| **User auth / accounts** | Auth at hackathon scope is 2-4 hours of implementation that contributes zero demo value. The demo judges do not care that the product is single-user | Every competitor ships with auth; for a hackathon demo it's pure overhead | OUT OF SCOPE (explicit) |
| **Rich source viewer** | A full document viewer (PDF renderer, scroll position, highlight sync) is a 1-week feature minimum. Readwise does it well and it's not Cortex's core | Source text accessible via citations only — still answers "where did this come from?" | OUT OF SCOPE (explicit) |
| **WebSocket / SSE real-time updates** | 5s polling is imperceptible to human users watching a graph update. Real-time infra adds complexity for zero perceptible user benefit at demo scale | No competitor requires sub-5s latency for background processing feedback | OUT OF SCOPE (explicit) |
| **Mobile responsive** | macOS notch app requires a Mac; the student is at a desk. A mobile-responsive graph is wasted effort; React Flow on mobile is also terrible | Most knowledge graph tools are desktop-first anyway | OUT OF SCOPE (explicit) |
| **Collaboration / multi-user** | Second brain tools that added sharing (Roam) fragmented their user base and slowed core product development | Notion's collaboration is its feature; for SRS, collaboration creates card quality diffusion | OUT OF SCOPE (explicit) |
| **Upstream NotchDrop features expansion** | The notch app is an ingestion pipe, not a product surface; extending it beyond the Cortex module creates maintenance burden | NotchDrop already handles file-shelf use cases; Cortex's job is the drop-to-graph pipeline | OUT OF SCOPE (explicit) |
| **Streaming LLM responses** | Background tasks (concept extraction, card generation) don't need streaming; the graph updates via poll anyway | No educational product streams extraction results | OUT OF SCOPE (explicit) |

---

## Feature Deep-Dives: Implementation Quality Signals

These are NOT new features. They are quality thresholds that determine whether the features Cortex already has will feel polished or broken.

### Anki SRS Review Session UX — What Makes It Feel Right

Anki's review session has been refined over 15+ years. The patterns students have internalized:

1. **Front-only until deliberate reveal.** The card front is shown; the answer is hidden by default behind a "Show Answer" button or spacebar. Users judge themselves before seeing the answer. Revealing before judging ruins the retrieval practice effect. Cortex spec matches this.

2. **Grading scale is 4 options, not a slider.** Anki uses Again/Hard/Good/Easy (mapped to 1/2/3/4 in Anki, but 1/3/4/5 in SM-2). The labels matter more than the numbers. "Again" is unambiguous (failed recall); "Easy" means "too easy, penalize me less." Cortex's internal grades 1/3/4/5 should surface as **Again / Hard / Good / Easy** in the UI — don't show numbers or invent new labels.

3. **Per-button "next interval preview."** Anki shows the next due interval under each grade button before the user clicks (e.g., "Again: 10min | Hard: 1d | Good: 4d | Easy: 8d"). This is a HIGH-value trust signal: students understand the SRS is doing something rational. This is NOT in the Cortex spec — it's a polish addition worth doing in the Study page.

4. **Session completion state.** When the queue is empty, Anki shows "Congratulations! You have finished this deck for now." with stats (time spent, cards reviewed, % correct). Without this, students don't know if they're done or if the app is broken. The spec implies a progress bar but doesn't define the zero-queue state explicitly.

5. **"Undo last card" escape hatch.** Anki allows undoing the last grade. Students fat-finger grades; without undo, one misclick permanently skews their schedule. Not in Cortex spec — low priority for hackathon but worth noting.

6. **Card types don't require different UI.** Definition, application, gotcha, compare — all are still a front/back pair from the UX perspective. The student doesn't see "type: gotcha"; they see the question. The card generation logic produces different question phrasings, but the review UI is identical. This simplifies the Study page.

### Knowledge Graph UX — Node/Edge/Panel Conventions

From Obsidian, Roam, Logseq, and Remnote's graph views:

1. **The graph is navigation, not content.** Obsidian and Roam both show graphs that look impressive but have low navigational utility because nodes are file names and there's no semantic differentiation. Cortex's graph is semantically differentiated (node size = source_count, color = mastery, pulsing = struggle) — this is what makes it useful rather than decorative.

2. **Click-to-panel, not click-to-navigate.** In Obsidian's graph, clicking a node navigates INTO the note and leaves the graph. This is disorienting. The correct pattern for Cortex is click-to-panel (slide-in side panel) while the graph remains visible. The spec describes a Node detail panel — implementation should be a right-side drawer, not a page navigation.

3. **Hover labels are required.** Small nodes in a force-directed graph are unreadable without hover tooltips showing the concept name. React Flow supports this natively. Forget this and the graph is unusable with more than ~20 nodes.

4. **Force-directed vs. dagre layout tradeoffs.** Roam and Obsidian use force-directed layouts; they look organic but become tangled with interconnected nodes. The spec uses dagre layout by depth (BFS from course root) — this is the correct call for a course knowledge graph because it shows prerequisite chains clearly. Dagre produces a DAG-like layout that teaches the student what they need to learn first.

5. **Node sizing by connection count.** Obsidian sizes nodes by number of backlinks. Cortex sizes by source_count. Both communicate "how important/referenced is this concept?" — students have already seen this idiom.

6. **Edge types need visual differentiation.** "contains" vs "prerequisite" vs "related" are meaningfully different. Competitors rarely differentiate edge types visually (they use single edge style). Cortex should use at minimum: solid line for prerequisite (directional, with arrowhead), dashed line for related (undirected or lighter). "contains" (course → concept) edges are implicit from the dagre layout and can be de-emphasized.

### "Weak Spots" Quiz — Compelling vs. Gimmicky

Remnote has a "Practice Weak Items" feature. Readwise has "Mastery Challenges." Both feel gimmicky because:
- They surface cards that aren't contextualized ("you got this card wrong twice" is not motivating)
- The quiz feels like punishment rather than diagnosis

What makes weak-spots feel compelling:
1. **Name the concepts, not just cards.** "You'll be quizzed on: Gradient Descent, Overfitting, Regularization" before starting makes the quiz feel targeted. The student sees concepts they recognize and can calibrate expectations. The spec's quiz results show "concepts to review" — surfacing them BEFORE the quiz starts (on the launch screen) is a quality improvement.
2. **Show mastery delta after quiz.** After results, showing "Gradient Descent: 0.3 → 0.6" makes the quiz feel like it did something. The spec updates mastery_score but the frontend needs to surface before/after explicitly.
3. **"Generate quiz" from a node panel** is the right entry point — the student is already looking at a red node and the contextual action is natural. The spec has this button in the node detail panel.
4. **Quiz length matters.** 5-10 questions is the sweet spot for a "targeted" quiz; 20+ feels like an exam. The spec accepts `num_questions` — the default should be 7-10 for `weak_spots` scope.

### NotchDrop-Style Drop Zone — User Expectations

The "drop and forget" workflow is borrowed from clipboard managers and file-shelf apps:

1. **Instant acknowledgment, async processing.** The user drops and gets feedback within ~200ms that the item was received. Processing can take 30-120s in the background. The spec has this right: "returns `{source_id, status: 'pending'}` immediately." The notch pill (Sending → Sent → Error) must be visible immediately and persist long enough to read (~3s for Sent, indefinite for Error).

2. **Drop target must be visually discoverable.** NotchDrop uses the macOS notch as a drop target — it activates when the user drags near the notch area. Students unfamiliar with the workflow need affordance: the notch should highlight/expand when a drag is in progress near it. This is handled by the existing NotchDrop code; Cortex shouldn't change this behavior.

3. **Error recovery.** If the status pill shows Error, the student needs to know what to do. The spec records `status=error + stack trace summary` in the backend, but the notch pill should show something actionable: "Error — try again" rather than a generic error state.

4. **Accepted file type feedback.** Dragging an unsupported file type (e.g., `.zip`) should give immediate feedback rather than silently creating a failed source row. This is a polish item not currently in the spec.

5. **The fallback to NotchDrop shelf is the safety net.** When Cortex is disabled, the notch reverts to normal file-shelf behavior. This eliminates the "I broke my notch" concern students would have about installing a fork.

### Student Study Workflow Patterns — SRS Scheduling Implications

Research on student study behavior (from cognitive science literature represented in training data):

1. **Study sessions cluster around deadlines, not optimal intervals.** Students overwhelmingly study before exams, not on SM-2's schedule. This means:
   - The due-today count will spike before midterms/finals as cards pile up
   - The spec's SM-2 default intervals are correct; no modification needed
   - The frontend should handle large queues gracefully (session with 80 due cards should still show clear progress)

2. **Most study sessions are short (10-20 min).** Students study in transit, between classes, waiting in lines. A good review session shouldn't require completing the entire queue — Anki allows stopping mid-session. The spec's study page doesn't define interruption handling. Cards reviewed are already committed (POST /flashcards/{id}/review is per-card), so stopping mid-session is safe. But the UI should not imply "you must finish all N cards."

3. **Evening review is most common.** SRS scheduling defaults should set `due_at` such that new cards become due the next day morning (not 10 minutes after creation, which would interrupt an active ingestion session with study prompts). The spec auto-generates cards when a concept is created — interval_days=1 for new cards via SM-2 means they're due the next day, which is correct.

4. **Students re-drop content they already have.** Lecture slides get updated; students download v2 and drag it in. The content_hash deduplication is the right mechanism — but the frontend should confirm "This content already exists" rather than silently doing nothing.

---

## Feature Dependencies

```
Ingestion (Drop/Clipboard)
    → Source created (status=pending)
        → Pipeline: parse → chunk → embed → extract concepts
            → Concepts created
                → Flashcards generated (3-6 per concept)    ← SRS session depends on this
                → Graph nodes populated                      ← Graph view depends on this
                    → Mastery initialized (0.5)
                        → Mastery updated by reviews         ← Struggle detection depends on mastery history
                            → Struggle signals computed      ← Weak-spots quiz depends on struggle/mastery
                                → Quiz generation            ← Quiz page depends on this

Dashboard (cards due today)
    → Requires: flashcards with due_at populated
    → Requires: at least one course with concepts

Node detail panel
    → Requires: graph nodes with summary/gotchas/key_points populated (LLM extraction)
    → "Review" button → Study page for this concept's cards
    → "Generate quiz" button → Quiz page for this concept

Graph visualization
    → Requires: course + concepts + edges
    → Requires: mastery scores for color
    → Requires: struggle signals for pulsing dot

Weak-spots quiz
    → Requires: mastery scores with variance (seed data provides this for demo)
    → Requires: bottom-quartile concepts identified
    → Quiz page → results → mastery delta display
```

**Critical path for demo readiness:**
1. Ingestion pipeline must produce real concepts (not empty/garbage)
2. Flashcard quality must feel tutor-grade (not "Q: What is X? A: X is X.")
3. Graph must render with enough nodes to look interesting (seed data: CS229 3 PDFs = ~30-50 concepts)
4. Mastery variance must be present in seed data (otherwise the graph is all yellow, weak-spots quiz is uninformative)

---

## MVP vs. Demo-Critical vs. Nice-to-Have

| Feature | Category | Demo-Critical? | If Cut, Impact |
|---------|----------|----------------|----------------|
| Notch drop (PDF, URL) | Differentiator | YES | Loses the opening demo moment |
| Auto concept graph | Differentiator | YES | Core value proof |
| SRS review session (Study page) | Table stakes | YES | Can't claim SRS product without it |
| Weak-spots quiz button | Differentiator | YES | The "killer button" |
| Node detail panel with gotchas | Differentiator | YES | Shows AI quality beyond flashcards |
| Graph mastery coloring | Table stakes (once graph exists) | YES | Without color it's just a node diagram |
| Struggle signals (pulsing dot) | Differentiator | YES | Uniquely visual demo moment |
| Dashboard (cards due, weak concepts) | Table stakes | YES | Entry point to studying |
| Clipboard ingestion (⌘V) | Differentiator | MEDIUM | Less demo impact than drag; secondary |
| Image ingestion + Claude OCR | Table stakes for the vision claim | MEDIUM | If dropped: URL + PDF still demo cleanly |
| Library page (source list) | Table stakes | MEDIUM | Students need to verify what was ingested |
| Session empty-queue completion state | Table stakes | LOW | Missing = mild confusion, not demo failure |
| Per-grade interval preview (Anki-style) | Polish | LOW | Nice but not table stakes for hackathon |
| Undo last card grade | Polish | LOW | Fat-finger protection; not demo-critical |
| Pre-quiz concept list | Polish | LOW | Nice UX but quiz still works without it |
| Mastery delta display post-quiz | Polish | LOW | Adds to compelling-ness, not required |
| Deduplication UX feedback | Polish | LOW | Backend handles it; UI confirmation is polish |

---

## Missing Table-Stakes Check

Reviewing the spec against the competitor baseline for anything obviously absent:

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| **Empty-queue completion state on Study page** | MEDIUM | When `GET /flashcards/due` returns empty, show: "All caught up! 0 cards due. Next review: [timestamp of nearest due_at]." Not defining this risks showing a blank page. Add explicit spec requirement. |
| **Grade button labels in UI** | LOW | The spec uses grades 1/3/4/5 internally. The UI must map to "Again / Hard / Good / Easy" — this is implicit but should be explicitly defined to avoid a builder naming them "1/2/3/4" or "Bad/OK/Good/Great." |
| **Minimum viable error state for node panel** | LOW | If a concept has no summary yet (pipeline still running), the node panel must show a loading/pending state rather than empty fields. The spec defines polling for graph updates but doesn't define partial-concept UI state. |
| **"No courses yet" empty state on Dashboard** | LOW | A fresh install shows an empty dashboard. The "Create Course" button is there, but an explicit empty-state prompt ("Create your first course to get started") prevents confusion. Minor but worth noting. |

No critical table-stakes features are missing from the spec. The spec is well-constructed for a hackathon demo. The four gaps above are all LOW-MEDIUM polish items.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Anki SRS UX patterns | HIGH | Anki is extensively documented; patterns are stable and well-known through 2025 |
| Knowledge graph UX (Obsidian/Roam/Logseq) | HIGH | All mature products; graph UX conventions are stable |
| Remnote/Readwise feature comparison | HIGH | Both well-documented through training cutoff |
| Weak-spots quiz UX heuristics | MEDIUM | Reasoning from first principles + competitor observations; no live research available |
| Student study workflow patterns | MEDIUM | Based on cognitive science literature and UX research in training data; no live survey data |
| NotchDrop drop-zone expectations | MEDIUM | Based on clipboard/file-shelf app conventions; specific NotchDrop behavior inferred from description and GitHub familiarity |

---

## Sources

- Anki documentation and community knowledge (training data, extensively documented)
- Obsidian graph view UX (training data, official docs)
- Roam Research and Logseq graph conventions (training data)
- RemNote flashcard + weak items feature (training data)
- Readwise Reader highlight-to-card pipeline (training data)
- SM-2 algorithm specification (Piotr Wozniak's original 1987 paper, widely reproduced)
- NotchDrop (Lakr233/NotchDrop, MIT licensed, referenced in PROJECT.md)
- Cognitive science research on student study patterns: distributed practice, test effect (Roediger, Karpicke 2006; Ebbinghaus forgetting curve — both in training data)
