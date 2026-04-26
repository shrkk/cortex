"use client";

import {
  Search, Plus, LayoutTemplate, CreditCard, HelpCircle, BookOpen,
  Settings, X, ArrowRight, ArrowLeft, FileText, MessageSquare,
  Link, Image, Check, MoreHorizontal, Bookmark, Brain, Command,
  CornerDownLeft, Circle, ChevronLeft, ChevronRight, Upload, Loader,
  type LucideProps,
} from "lucide-react";
import React from "react";

// ── Icon ─────────────────────────────────────────────────────────────────────
const ICON_MAP: Record<string, React.ComponentType<LucideProps>> = {
  search:     Search,
  plus:       Plus,
  graph:      LayoutTemplate,
  cards:      CreditCard,
  quiz:       HelpCircle,
  library:    BookOpen,
  settings:   Settings,
  close:      X,
  arrowRight: ArrowRight,
  arrowLeft:  ArrowLeft,
  fileText:   FileText,
  message:    MessageSquare,
  link:       Link,
  image:      Image,
  check:      Check,
  more:       MoreHorizontal,
  bookmark:   Bookmark,
  brain:      Brain,
  command:    Command,
  return:     CornerDownLeft,
  dot:        Circle,
  prev:       ChevronLeft,
  next:       ChevronRight,
  upload:     Upload,
  loader:     Loader,
};

export function Icon({
  name,
  size = 18,
  color = "currentColor",
  className,
}: {
  name: string;
  size?: number;
  color?: string;
  className?: string;
}) {
  const Component = ICON_MAP[name] ?? Circle;
  return (
    <Component
      width={size}
      height={size}
      stroke={color}
      strokeWidth={1.5}
      style={{ flexShrink: 0, color }}
      className={className}
    />
  );
}

// ── Button ────────────────────────────────────────────────────────────────────
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize    = "sm" | "md" | "lg";

const VARIANTS: Record<ButtonVariant, React.CSSProperties> = {
  primary:   { background: "var(--accent)",   color: "var(--accent-ink)", border: "none" },
  secondary: { background: "var(--surface)",  color: "var(--ink)",       border: "1px solid var(--border)" },
  ghost:     { background: "transparent",     color: "var(--ink-muted)", border: "none" },
  danger:    { background: "var(--surface)",  color: "var(--mastery-low)", border: "1px solid var(--border)" },
};

const SIZES: Record<ButtonSize, React.CSSProperties> = {
  sm: { padding: "5px 12px",  fontSize: 12.5 },
  md: { padding: "8px 16px",  fontSize: 13.5 },
  lg: { padding: "11px 20px", fontSize: 14.5 },
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  icon,
  onClick,
  disabled,
  type = "button",
  style,
}: {
  children?: React.ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: string;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  style?: React.CSSProperties;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        borderRadius: 6,
        fontFamily: "var(--font-sans)",
        fontWeight: 500,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "background 200ms var(--ease), border-color 200ms var(--ease), opacity 200ms var(--ease)",
        lineHeight: 1.2,
        ...VARIANTS[variant],
        ...SIZES[size],
        ...style,
      }}
    >
      {icon && <Icon name={icon} size={size === "sm" ? 14 : 16} />}
      {children}
    </button>
  );
}

// ── Pill / Badge ──────────────────────────────────────────────────────────────
type PillTone = "neutral" | "high" | "mid" | "low" | "info" | "accent";

const TONES: Record<PillTone, { bg: string; fg: string; dot: string }> = {
  neutral: { bg: "var(--surface-sunken)", fg: "var(--ink-muted)",  dot: "var(--ink-faint)" },
  high:    { bg: "var(--mastery-high-soft)", fg: "#3F5A33", dot: "var(--mastery-high)" },
  mid:     { bg: "var(--mastery-mid-soft)",  fg: "#7A5524", dot: "var(--mastery-mid)" },
  low:     { bg: "var(--mastery-low-soft)",  fg: "#7A3826", dot: "var(--mastery-low)" },
  info:    { bg: "var(--info-soft)",    fg: "#3D556B", dot: "var(--info)" },
  accent:  { bg: "var(--accent-soft)", fg: "#A54E31", dot: "var(--accent)" },
};

export function Pill({
  tone = "neutral",
  dot,
  children,
}: {
  tone?: PillTone;
  dot?: boolean;
  children: React.ReactNode;
}) {
  const t = TONES[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        background: t.bg,
        color: t.fg,
        padding: "3px 10px",
        borderRadius: 999,
        fontFamily: "var(--font-sans)",
        fontSize: 11.5,
        fontWeight: 500,
        whiteSpace: "nowrap",
      }}
    >
      {dot && (
        <span
          style={{ width: 6, height: 6, borderRadius: 999, background: t.dot, flexShrink: 0 }}
        />
      )}
      {children}
    </span>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────
export function Card({
  children,
  padding = 24,
  hoverable,
  onClick,
  style,
}: {
  children: React.ReactNode;
  padding?: number;
  hoverable?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
}) {
  const [hover, setHover] = React.useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover && hoverable ? "var(--surface-hover)" : "var(--surface)",
        border: `1px solid ${hover && hoverable ? "var(--border-strong)" : "var(--border)"}`,
        borderRadius: 12,
        padding,
        cursor: onClick ? "pointer" : "default",
        transition: "background 200ms var(--ease), border-color 200ms var(--ease)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ── Eyebrow ───────────────────────────────────────────────────────────────────
export function Eyebrow({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        color: "var(--ink-muted)",
        fontWeight: 500,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ── Kbd ───────────────────────────────────────────────────────────────────────
export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 11,
        fontWeight: 500,
        background: "var(--surface)",
        color: "var(--ink-soft)",
        border: "1px solid var(--border-strong)",
        borderBottomWidth: 2,
        borderRadius: 4,
        padding: "1px 6px",
      }}
    >
      {children}
    </kbd>
  );
}
