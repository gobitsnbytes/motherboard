# Plan: Motherboard onboarding series (5 videos)

Audience: volunteers, collaborators and execs. Goal: explain what each feature is, why we use it and how it works. Plain text, no jargon.

Format: 1920x1080, 39s each. Tone: calm and clear. Brand cream/burgundy/orange, Anton + Inter + JetBrains Mono, neobrutalist cards with hard shadows (from packages/ui + DESIGN.md).

## Same outline in every video
The top bar shows WHAT · WHY · HOW and lights up the current section. A progress bar runs along the bottom.

| Scene | Time | Content |
|---|---|---|
| Title | 0–4s | "Onboarding 0N / 05", topic, one-line subtitle, the 3-part outline |
| What | 4–12s | One sentence + a grey placeholder mockup with real UI labels |
| Why | 12–20s | 3 reason cards, revealed one by one (each stays up 4–7s) |
| How | 20–35s | 4–5 numbered steps; the current step is highlighted and the mockup builds alongside |
| Remember | 35–39s | One takeaway + where to find it |

## Videos (all copy checked against the code)
1. **Signing in**: Discord OAuth via NextAuth. "Continue with Discord", Authorize, member match, `/dashboard/overview`.
2. **Permissions**: permission, grant, scope (global or `fork:delhi`), expiry. Discord role → group → grants. "Missing permission: X on Y".
3. **Onboarding**: "Start a case" (Volunteer / Fork lead), private link, document states, HQ finalizes. 13+ and guardian consent.
4. **Signatures**: bnb-signatures. Upload, signers and fields, "Finalize & Send Links", 6-digit email PIN, "Executed & Sealed", `/verify`.
5. **Calendar pools**: Cal.com routing pools. Connect a host, create a pool (Round robin), add hosts, share `/book/<slug>`. Chrono is legacy, read-only.

## Audio
Music: happy-beats vol-12, fades in over 1.2s and out over the last 1.8s. It sits at 0.22 volume in the background. Sound effects are subtle: a soft bell on the title, a drop on each section change and each reason card, and a click on each step. Timing is set for easy reading rather than locked to the beat.

Source: `build.ts` generates every composition from one template. Edit the copy there and run `bun build.ts` to rebuild.
