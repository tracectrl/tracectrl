---
name: TraceCtrl
description: Security observability and runtime control for AI agents
colors:
  signal-red: "#FC0404"
  signal-red-hover: "#FF2D2D"
  signal-red-melon: "#FCBEBE"
  command-jade: "#40706C"
  void-black: "#040404"
  surface-base: "#111111"
  surface-card: "#161616"
  surface-elevated: "#0A0A0A"
  border-subtle: "#222222"
  text-primary: "#F5F5F5"
  text-secondary: "#AAAAAA"
  text-muted: "#6B6B6B"
  text-faint: "#8A8A8A"
  risk-critical: "#FF4D4D"
  risk-high: "#FF6B35"
  risk-medium: "#FFBB00"
  risk-low: "#22C55E"
typography:
  display:
    fontFamily: "'Poppins', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "48px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "'Poppins', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "'Poppins', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.2
  body:
    fontFamily: "'Poppins', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.10em"
  mono:
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  sm: "6px"
  md: "10px"
  lg: "12px"
spacing:
  1: "4px"
  2: "8px"
  3: "12px"
  4: "16px"
  5: "20px"
  6: "24px"
  8: "32px"
  10: "40px"
  12: "48px"
  16: "64px"
components:
  badge-critical:
    backgroundColor: "rgba(255, 77, 77, 0.12)"
    textColor: "{colors.risk-critical}"
    rounded: "4px"
    padding: "3px 8px"
  badge-high:
    backgroundColor: "rgba(255, 107, 53, 0.12)"
    textColor: "{colors.risk-high}"
    rounded: "4px"
    padding: "3px 8px"
  badge-medium:
    backgroundColor: "rgba(255, 187, 0, 0.12)"
    textColor: "{colors.risk-medium}"
    rounded: "4px"
    padding: "3px 8px"
  badge-low:
    backgroundColor: "rgba(34, 197, 94, 0.12)"
    textColor: "{colors.risk-low}"
    rounded: "4px"
    padding: "3px 8px"
  badge-agent:
    backgroundColor: "rgba(64, 112, 108, 0.15)"
    textColor: "{colors.command-jade}"
    rounded: "4px"
    padding: "3px 8px"
  card:
    backgroundColor: "{colors.surface-card}"
    rounded: "{rounded.lg}"
    padding: "24px"
  card-hover:
    backgroundColor: "{colors.surface-card}"
    rounded: "{rounded.lg}"
    padding: "24px"
---

# Design System: TraceCtrl

## 1. Overview

**Creative North Star: "The Control Tower"**

TraceCtrl is a high-stakes precision instrument. The people using it are watching over complex, potentially compromised AI systems. The interface reflects that responsibility: information-dense but never chaotic, authoritative but never alarming. A security engineer opens this dashboard in the middle of the night and needs to know, within seconds, whether something is wrong, what it is, and where to look. The design earns trust by showing its work.

Red is the commanding voice of this system. It leads hierarchy, appears in section tags, active navigation, and violation signals. It's not a warning color here — it's a leadership color, the visual spine that keeps eyes moving in the right direction. The dark surfaces absorb everything else: jade reads as measured confirmation, orange and yellow as elevation warnings, white text as signal, gray as context. Nothing competes with red for attention.

This is a dark-native product. The physical scene: an engineer or SOC analyst at a large monitor, ambient room lighting low, watching agent behavior over time. Light mode is a quality citizen for daylight use, but dark is the native state. The system should never feel like a generic SaaS dashboard, a 2012 SIEM report viewer, or a threat-visualization theater piece. It should feel like a tool that genuinely understands the domain.

**Key Characteristics:**
- Dark-first tonal layering: depth through surface steps, not shadows
- Red as a leadership accent, jade as secondary confirmation, risk palette for severity
- Dense information hierarchy through scale and weight contrast, not whitespace padding
- Monospaced type (JetBrains Mono) for all data, IDs, counts, and timestamps
- Flat at rest; state (hover, active, selected) reveals structure

## 2. Colors: The Control Room Palette

A disciplined four-role palette: one commanding accent, one confirmation secondary, a structured neutral stack, and a purpose-built risk scale.

### Primary
- **Signal Red** (`#FC0404`): The spine of the interface. Used for the active nav indicator, section tags, focus rings, critical violation badges, and primary action buttons. Its rarity on data surfaces (charts, tables, metadata) preserves its authority when it does appear.
- **Signal Red Hover** (`#FF2D2D`): Interactive state on red elements. Slightly lighter, slightly warmer.
- **Signal Red Melon** (`#FCBEBE`): Washed-out pink used sparingly for illustrated states, empty-state accents, or as a background tint in high-severity alert drawers.

### Secondary
- **Command Jade** (`#40706C`): The confirmation color. Used on guarded-agent indicators, "active" health badges, topology nodes with guardrails attached, and secondary interactive elements. Reads as measured safety, the opposite of red's urgency.

### Neutral
- **Void Black** (`#040404`): The deepest surface. Page/canvas background.
- **Surface Base** (`#111111`): Sidebar and primary surface layer.
- **Surface Card** (`#161616`): Cards, panels, drawers, and data containers.
- **Surface Elevated** (`#0A0A0A`): Inputs, code blocks, inset surfaces.
- **Border Subtle** (`#222222`): All dividers, card borders, and separator lines.
- **Text Primary** (`#F5F5F5`): Headlines, values, primary labels.
- **Text Secondary** (`#AAAAAA`): Body copy, supporting text.
- **Text Muted** (`#6B6B6B`): Timestamps, metadata, secondary counts.
- **Text Faint** (`#8A8A8A`): Inactive nav items, placeholders.

### Risk Scale
Four-step severity palette, applied exclusively to risk/violation signals. Never used decoratively.
- **Critical** (`#FF4D4D`): Prompt injection, policy bypass, immediate threat.
- **High** (`#FF6B35`): Rule violations, guardrail failures.
- **Medium** (`#FFBB00`): Suspicious patterns, anomalies.
- **Low** (`#22C55E`): Informational, clean state, pass results.

### Named Rules
**The One Voice Rule.** Signal Red is the primary voice. Every other color defers to it. When red appears, eyes go there. Protect that reflex by keeping red off neutral content (body text, table rows, metadata) where its presence would degrade the signal.

**The Risk Isolation Rule.** The four risk colors exist solely for severity communication. Using `--risk-low` green for non-risk success states, or `--risk-medium` amber for warnings unrelated to agent security, corrupts the vocabulary. Use jade for non-risk confirmations; use the risk scale only when reporting violation or health state.

## 3. Typography

**Display Font:** Poppins (with -apple-system, BlinkMacSystemFont fallback)
**Body Font:** Poppins (same family; weight differentiates roles)
**Data/Mono Font:** JetBrains Mono (with Fira Code fallback)

**Character:** A humanist geometric sans for headings and body — clean, slightly warm, confident without being loud. JetBrains Mono everywhere data appears: IDs, counts, trace lengths, timestamps, code. The contrast between Poppins and JetBrains Mono creates a clear register divide: Poppins is language, JetBrains Mono is machine output.

### Hierarchy
- **Display** (800 weight, 48px, 1.1 line-height, -0.02em tracking): Page titles only. Used once per page.
- **Headline** (700 weight, 32px, 1.2 line-height): Section headings, major panel titles.
- **Title** (600 weight, 18px, 1.2 line-height): Card titles, drawer headings, subsection labels.
- **Body** (400 weight, 14px, 1.6 line-height): All descriptive copy, metadata, reasoning text. Line length capped at 65-75ch.
- **Label** (700 weight, 10-11px, uppercase, 0.08-0.12em tracking): Section tags, badge text, table column headers, sidebar section dividers. JetBrains Mono for data labels; Poppins for category labels.
- **Mono Data** (400 weight, 13px, 1.6 line-height): All values, IDs, span counts, durations, hashes. JetBrains Mono.

### Named Rules
**The Register Divide Rule.** Poppins for human-readable language; JetBrains Mono for machine-readable data. Never use a serif or decorative font. Never render a trace ID, agent count, or timestamp in Poppins.

**The Weight Contrast Rule.** Scale steps must carry a weight shift: 800/700 for display/headline, 600 for title, 400 for body. Avoid a flat-weight hierarchy where only size differentiates levels; the resulting scale looks anemic in a dense dashboard.

## 4. Elevation

TraceCtrl uses tonal surface layering, not shadows. Depth is expressed through background color steps: `void-black` (#040404) for the canvas, `surface-base` (#111111) for the sidebar, `surface-card` (#161616) for cards and panels, `surface-elevated` (#0A0A0A) for inset elements like inputs and code blocks. There are no `box-shadow` values in the base system.

The exception is alert-specific glow: a `--red-glow: rgba(252, 4, 4, 0.25)` and `--red-soft: rgba(252, 4, 4, 0.10)` that can appear as a background tint or faint spread under violation cards and toast notifications. This is semantic, not decorative.

### Named Rules
**The Flat-By-Default Rule.** No shadows at rest. Depth is a property of the surface stack, not of lighting simulation. If an element needs to feel "above" another element, change its background to a step lighter in the surface scale, not its shadow.

**The Glow Exception.** Faint red glow (`--red-glow`) is permitted on active violation alerts, toast notifications for HIGH/CRITICAL severity, and the topology node for agents with active guardrails (using jade glow). It is a functional signal, not an aesthetic choice. Do not apply glow to cards, buttons, or hover states in the general UI.

## 5. Components

### Buttons
Button styles signal confidence through solid color assignment and compact geometry.
- **Shape:** Gently rounded (6px radius / `--radius-sm`)
- **Primary:** Signal red background (`#FC0404`), white text (`#F5F5F5`), padding 10px 20px, Poppins 13px 600 weight. Hover shifts to `#FF2D2D`.
- **Secondary/Ghost:** Transparent background, `--dark-border` border, text-secondary color. Hover: border shifts to `--gray-600`, text to text-primary.
- **Transition:** 150ms on background and border-color, `cubic-bezier(0.16, 1, 0.3, 1)`.

### Badges
Compact severity and type chips. Character: controlled density, small enough to stack, legible at a glance.
- **Shape:** 4px radius (sharper than cards; badges are data, not containers)
- **Text:** 10px, 700 weight, uppercase, 0.06em letter-spacing. JetBrains Mono preferred.
- **Risk badges:** Translucent tinted background at 12% opacity of the risk color. Text is the full-opacity risk color.
- **Agent/type badges:** Jade soft background, jade text for agents. Gray-800 background, gray-400 text for tools and neutral types.
- **Never use solid risk colors as badge backgrounds.** The 12% translucency is the rule; full-saturation risk badges feel alarming rather than informative.

### Cards / Containers
- **Corner Style:** 12px radius (`--radius-lg`)
- **Background:** `surface-card` (#161616)
- **Shadow Strategy:** None. See Elevation.
- **Border:** 1px `border-subtle` (#222222)
- **Internal Padding:** 24px (`--space-6`) standard; 20px/24px (`--space-5`/`--space-6`) for stat cards.

### Inputs / Fields
- **Style:** `surface-elevated` (#0A0A0A) background, 1px `border-subtle` border, `--radius-sm` (6px) corners
- **Focus:** 2px `signal-red` outline, 2px offset
- **Placeholder:** `text-muted` (#6B6B6B) color
- **Mono content (search, ID fields):** JetBrains Mono 13px

### Navigation (Sidebar)
- **Default state:** 13px Poppins 500, `text-faint` (#8A8A8A), 2px transparent left border, padding 9px 24px
- **Hover:** `text-primary` (#F5F5F5) color, no border change
- **Active:** `signal-red` (#FC0404) text and left border (2px). This is the single purposeful left-border exception: navigation position indicators are functional, not decorative.
- **Section dividers:** 10px Poppins 700 uppercase, 0.12em tracking, `text-muted` color

### Section Tag (Signature Component)
A distinctive structural element: a 20px × 2px red rule followed by uppercase red type. Appears as the eyebrow label above every page heading.
- 11px Poppins 700, `signal-red`, uppercase, 0.12em tracking
- Preceded by `::before` pseudo-element: `width: 20px; height: 2px; background: signal-red`
- Used exactly once per page section header. Not for body content labels.

### Severity Badges in Context (Signature Component)
The risk badge + short text pattern is the core readout of the Alerts and Guardrails pages.
- Always: badge on the left, name on the right, never the reverse
- Severity badge must precede the guardrail name or violation title in all list/table contexts

## 6. Do's and Don'ts

### Do:
- **Do** use Signal Red (`#FC0404`) to lead visual hierarchy: section tags, active nav, primary buttons, and violation headlines. Its commanding presence is intentional.
- **Do** use JetBrains Mono for all machine-readable data: trace IDs, span counts, durations, timestamps, hashes. Never Poppins for these.
- **Do** express depth through the surface stack (`#040404` → `#111111` → `#161616`), not through shadows or blurs.
- **Do** use 12% translucent backgrounds for risk badges. The tint reads clearly without feeling like an alarm.
- **Do** reserve the four risk colors (`--risk-critical` through `--risk-low`) exclusively for agent/guardrail severity signals. Use jade for non-risk success states.
- **Do** apply the Section Tag pattern (red rule + red uppercase label) as the standard page heading eyebrow. Consistency here is what makes the pattern legible.
- **Do** keep body line length to 65-75ch on any block of descriptive text (reasoning fields, evidence copy, system prompt display).
- **Do** use `cubic-bezier(0.16, 1, 0.3, 1)` for all transitions. Exponential ease-out; no bounce, no elastic.

### Don't:
- **Don't** build the UI to look like Splunk or legacy SIEM dashboards: dense gray tables with no hierarchy, no accent color, everything the same weight. TraceCtrl is not a report viewer.
- **Don't** dramatize risk with Wiz-style 3D attack graph theater or aggressive red everywhere. Violations are precise facts, not emergencies. Surface them calmly.
- **Don't** build generic SaaS widget grids where every card is the same size, same icon, same structure. Information density should vary with the importance of what's being shown.
- **Don't** use `border-left` or `border-right` greater than 1px as a colored accent on cards, list items, callouts, or alerts. The active nav indicator is the sole exception, and it is a navigation affordance, not a design decoration.
- **Don't** use `background-clip: text` with gradient backgrounds for any text element. Emphasis through weight and size only.
- **Don't** use glassmorphism (blurs, semi-transparent panels) decoratively. The surface stack achieves depth without frosted glass.
- **Don't** use the hero-metric template (large centered number, small label, gradient accent) as a dashboard pattern. TraceCtrl's data tables and trace trees are the primary content; summaries are navigation aids, not the story.
- **Don't** apply the risk color scale to non-security signals. A "success" state in a UI form doesn't use `--risk-low` green; use jade or neutral confirmation patterns instead.
- **Don't** render in light mode as an afterthought: every new component must be explicitly tested with `[data-theme="light"]` overrides. Surface variables (`--dark-card`, `--dark-border`, etc.) switch automatically; hardcoded hex values in Cytoscape-style inline styles must be explicitly overridden.
