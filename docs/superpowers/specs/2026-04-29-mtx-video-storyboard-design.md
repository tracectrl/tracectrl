# MTX Presentation Video — Storyboard Design
**Date:** 2026-04-29  
**Event:** MTX — Trustworthiness in Agentic AI Systems  
**Duration:** ~3 minutes  
**Format:** HeyGen segments + screen recordings, edited together  
**Audience:** Mixed — security engineers and business/exec decision-makers  

---

## Video Goal

Demonstrate TraceCtrl as the observability and guardrails layer for agentic AI systems using FinFlow (a real multi-agent invoice processing pipeline) as the live demo. Show a clean run, then a prompt injection attack that bypasses controls, then prove TraceCtrl caught it and can block it.

Tagline anchor: **See. Trace. Alert.**

---

## Assets Available

- `videos/tracectrl-intro/renders/tracectrl-intro.mp4` — existing TraceCtrl intro, reuse as visual backdrop or splice into Scene 1
- `tracectrl-demo/finflow/` — live FinFlow agent system
- `tracectrl-demo/finflow/demo/attack1_pdf_generator.py` — generates malicious PDF for ATK-1
- `tracectrl-demo/finflow/demo/happy_path_runner.py` — runs clean invoice flow

---

## Design System

Match the existing intro video style exactly:

| Token | Value |
|---|---|
| Canvas | `#040404` |
| Card backgrounds | `#111111` |
| Primary red | `#FC0404` |
| Primary text | `#F5F5F5` |
| Secondary text | `#8A8A8A` |
| Display font | Poppins 700/800 |
| Mono font | JetBrains Mono |
| Transition | Blur crossfade 0.5s `power2.inOut` |

No gradients. No emoji. No stock icons. Red is the only chromatic accent.

---

## Scene Breakdown

### Scene 1 — HeyGen · ~40s
**"What is TraceCtrl + What is FinFlow"**

**Type:** HeyGen talking-head with HyperFrames visual overlay  
**Reuse:** Splice or backdrop the existing `tracectrl-intro.mp4`

**Script:**
> "AI agents are making real decisions — processing invoices, verifying vendors, executing payments. But when something goes wrong inside that chain, who's watching?
>
> TraceCtrl gives you agentic observability. See every agent. Trace every decision. Alert on every anomaly.
>
> Today we're using FinFlow — an AI-powered invoice processing platform. It takes invoices through six agents: document parsing, policy validation, vendor intelligence, risk screening, and payment execution. A realistic enterprise workflow. And a realistic attack surface."

**Visual direction:**
- FinFlow architecture diagram animates agent by agent (Orchestrator → DocAI → PolicyAgent → VendorIntel → RiskAgent → PaymentAgent)
- Red line traces the path to PaymentAgent as the narrator says "realistic attack surface"
- Style: dark card, agent nodes in `#111111`, connector lines in `#1A1A1A`, PaymentAgent node pulses red on final beat

---

### Scene 2 — Screen Recording · ~40s
**"Happy Path — Everything Works"**

**What to show:**
1. Upload a clean invoice via FinFlow portal
2. TraceCtrl Agents view — watch each agent fire in sequence
3. Topology view — normal graph builds, all edges green
4. Brief pan over an agent's trace showing prompt + tool calls

**Narration (voiceover):**
> "Here's a normal run. Invoice comes in, each agent does its job, payment executes. TraceCtrl sees every hop, every tool call, every prompt. This is your baseline."

**Recording notes:**
- Keep UI clean — close any dev panels before recording
- Zoom in on the Topology graph briefly to show the established baseline path
- Aim for ~40s total including agent firing sequence

---

### Scene 3 — Screen Recording · ~55s
**"The Attack — Malicious PDF Bypasses Everything"**

**What to show:**
1. Generate `malicious_invoice.pdf` (or have it pre-generated)
2. Upload via FinFlow portal
3. TraceCtrl Agents view — DocAI fires, then anomalous path: PolicyAgent and RiskAgent skipped/overridden
4. PaymentAgent executes — unauthorized payment
5. Pause on Topology view — show divergence from baseline path

**Narration (voiceover):**
> "Now we upload an invoice with hidden instructions embedded in the PDF. The DocAI agent extracts the text — including the injected payload. The orchestrator follows it. Policy validation? Skipped. Risk screening? Bypassed. Payment executes. Unauthorized."

**Recording notes:**
- Pause 2-3s on the anomalous Topology graph after payment executes — let it land
- If possible, highlight the divergent path in red before cutting

---

### Scene 4 — Screen Recording · ~25s
**"TraceCtrl Caught It — But Was in Monitor Mode"**

**What to show:**
1. TraceCtrl Alerts tab — guardrail violation is logged
2. Highlight the alert: guardrail on path-to-PaymentAgent triggered
3. Show guardrail config panel — mode is `monitor`

**Narration (voiceover):**
> "TraceCtrl had a guardrail watching every path leading to the payment agent. It caught the violation — logged it right here. But we had it set to monitor mode. It saw it. It didn't stop it. That's a choice."

**Recording notes:**
- Hover over the alert to show detail (agent path, violation reason, timestamp)
- Briefly show the guardrail config — just enough to see "monitor" mode

---

### Scene 5 — HeyGen · ~20s
**"Switching to Block Mode + CTA"**

**Type:** HeyGen talking-head with screen capture overlay showing the UI toggle  
**Optional extension (~+10s):** Quick recording flash of a blocked run — agent halts mid-chain, red alert fires

**Script:**
> "This is the control TraceCtrl gives you. One setting. Switch the guardrail to block — now that same attack path gets terminated before PaymentAgent ever runs.
>
> Your agents. Your rules. Enforced in real time. That's trustworthy AI."

**Visual direction:**
- Show UI toggle animation: `monitor` → `block` with a red pulse on activation
- Final frame: TraceCtrl wordmark + tagline "See. Trace. Alert." on dark canvas

---

## Timing Summary

| # | Type | Label | Duration |
|---|---|---|---|
| 1 | HeyGen | TraceCtrl + FinFlow intro | ~40s |
| 2 | Recording | Happy path | ~40s |
| 3 | Recording | ATK-1 attack run | ~55s |
| 4 | Recording | Alert / monitor mode | ~25s |
| 5 | HeyGen | Block mode + CTA | ~20s |
| — | — | **Total** | **~3min** |

---

## HyperFrames Compositions Needed

Three HyperFrames compositions to build (Scenes 1 and 5 are HeyGen; Scene 1 needs the architecture diagram overlay):

| File | Purpose |
|---|---|
| `videos/mtx-demo/compositions/scene1-finflow-architecture.html` | FinFlow agent architecture diagram, animates node by node, red PaymentAgent pulse |
| `videos/mtx-demo/compositions/scene5-block-toggle.html` | Monitor→Block toggle animation + TraceCtrl CTA card |
| `videos/mtx-demo/index.html` | Root composition — orchestrates all scenes including recording placeholders |

---

## Production Order

1. Build HyperFrames compositions (Scenes 1 architecture overlay + Scene 5 CTA)
2. Record Screen 2 (happy path) — run `python demo/happy_path_runner.py`
3. Record Screen 3 (ATK-1) — run `python demo/attack1_pdf_generator.py` then upload
4. Record Screen 4 (alerts UI) — capture after ATK-1 run
5. Record Scene 5 optional extension (blocked run) — toggle guardrail to block, re-run ATK-1
6. Produce HeyGen videos for Scenes 1 and 5 using scripts above
7. Edit together in order: S1 → S2 → S3 → S4 → S5
