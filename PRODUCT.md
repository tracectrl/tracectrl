# Product

## Register

product

## Users

Two overlapping personas who often share a screen:

- **AI/ML engineers** who instrumented the agents: they open the dashboard to debug traces, verify guardrail coverage, and understand what their agents actually did.
- **Security engineers (SOC/AppSec)**: they come when something fires — reviewing violations, hunting attack paths, building confidence that the system is protected.

Both users are technically fluent. Neither wants hand-holding. The context is high-stakes but not always urgent: sometimes it's "why did this run fail?", sometimes it's "did that attack actually get stopped?". The dashboard needs to serve both calm investigation and rapid incident review.

## Product Purpose

TraceCtrl gives security teams and developers complete visibility into every AI agent action, tool call, and data access — with runtime guardrail protection and attack graph risk scoring.

It ingests OpenTelemetry traces from instrumented agent frameworks (Strands, LangChain, Agno, etc.) and surfaces inventory, topology, session forensics, guardrail status, and live violation alerts in one place. Success looks like: an engineer can go from "something looked wrong" to "here's the exact span, the injected payload, and the guardrail that caught it" in under 60 seconds.

## Brand Personality

Calm authority. Three words: **clear, precise, trustworthy**.

Not alarming — TraceCtrl should make scary things legible. Not clinical — it should feel like a tool built by people who understand the domain deeply. The interface earns trust through density done right: information is available when you need it, not thrown at you all at once.

## Anti-references

- **Splunk / legacy SIEM**: dense gray tables, no hierarchy, 2012 enterprise feel. TraceCtrl should never look like a report viewer.
- **Wiz / threat-map overload**: 3D attack graphs, aggressive red everywhere, more theater than utility. Risk should be surfaced calmly, not dramatized.
- **Generic SaaS dashboards**: blue-on-white, widget-grid sameness, looks like it could be for anything.

## Design Principles

1. **Calm over alarm.** Violations are important, not catastrophic. Severity communicates through precision (color, badge, evidence) — not by screaming.
2. **Density earns trust.** Engineers trust tools that show their work. Prefer detail-rich views with clear hierarchy over simplified summaries that hide what happened.
3. **Fast to the evidence.** Every interaction should reduce the distance between "something happened" and "here's exactly what it was." Navigation, drawers, trace links — all optimized for forensic speed.
4. **Dark-native, light-capable.** The primary mental model is a technical tool running on a dim monitor. Dark mode is the native state; light mode is a quality citizen, not an afterthought.
5. **Infrastructure confidence.** Looks like it belongs alongside Grafana, Datadog, and Linear — tools professionals depend on. Not a product demo, a production instrument.

## Accessibility & Inclusion

- WCAG AA minimum. Color is never the only signal for severity (always paired with label or icon).
- Support for reduced motion via `prefers-reduced-motion`.
- Both dark and light themes maintained at equivalent quality.
