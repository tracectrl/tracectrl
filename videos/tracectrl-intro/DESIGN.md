# TraceCtrl Intro Video — Design

## Style Prompt

Dark, security-native, authoritative. Tech/futuristic mood with tense undertones. 60-30-10 rule: mostly near-black canvas, crisp white/grey data, red as the alert/action accent. Editorial rhythm — stats land with weight, pillars compare cleanly, CTA breathes. No generic SaaS glow, no gradient wallpapers, no AI-hype visuals.

## Colors

- `#040404` — canvas (primary background)
- `#0A0A0A` — scene background variant (subtle contrast)
- `#111111` — card / pillar backgrounds
- `#1A1A1A` — border accent
- `#222222` — panel borders
- `#FC0404` — **primary red** — CTAs, critical stats, logo accent, alert pulses
- `#FF2D2D` — red hover / intensified moments
- `#FCBEBE` — melon (soft red, for subtle highlights)
- `#40706C` — jade (secondary accent, "trace" pillar)
- `#F5F5F5` — primary text (white)
- `#8A8A8A` — secondary text (gray-400)
- `#6B6B6B` — tertiary text (gray-500)
- `#FF4D4D` — risk critical (semantic)
- `#FFBB00` — risk medium (semantic)

## Typography

- **Poppins** — 700/800 for display, 500/600 for body, 700 uppercase with 0.12em tracking for section labels
- **JetBrains Mono** — for data labels, stats, code-like accents (check IDs, agent IDs)

## Motion Language

- **Energy:** medium — SaaS explainer pace. 0.4-0.6s entrance durations, 0.4-0.5s transitions.
- **Primary transition:** blur crossfade (0.5s, `power2.inOut`)
- **Accent transition:** push slide (scene 2 → 3, to signal "solution arrives")
- **Outro transition:** gentle blur crossfade (0.6s, `sine.inOut`)
- **Eases used:** `power3.out` for incoming text, `expo.out` for hero reveals, `power2.inOut` for transitions, `sine.out` for pulsing elements

## What NOT to Do

- No generic blue tech gradients — red is the ONLY chromatic accent, everything else is neutral.
- No full-screen linear gradients on dark backgrounds — they band under H.264 compression. Use solid fills with localized glow (radial).
- No emoji, no stock icons, no 3D renders. Data and typography only.
- No bouncy / elastic / playful eases — this is security, not a consumer app.
- No tagline before scene 4 — the viewer should feel the problem first.
