#!/usr/bin/env node
/**
 * Generate voiceover for the demo video using ElevenLabs TTS.
 *
 * Usage:
 *   export ELEVENLABS_API_KEY=sk_...
 *   node scripts/generate-voiceover.mjs
 *
 * Output: public/audio/voiceover.mp3
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

const API_KEY = process.env.ELEVENLABS_API_KEY;
if (!API_KEY) {
  console.error("❌ ELEVENLABS_API_KEY env var not set");
  console.error("   Run: export ELEVENLABS_API_KEY=sk_...");
  process.exit(1);
}

// Rachel — clear, professional, widely-liked female voice
// Swap to "TxGEqnHWrfWFTfGW9XjX" (Josh) for male narrator
const VOICE_ID = process.env.ELEVENLABS_VOICE_ID || "21m00Tcm4TlvDq8ikWAM";

// Full 3-minute script matching the scene timings in DemoVideo.tsx
// Timing guide (each ~paragraph aligns with a scene):
//   0:00-0:30  Intro
//   0:30-1:30  Consultant
//   1:30-2:15  Evidence Reviewer
//   2:15-2:45  Prescriber Agent
//   2:45-3:00  Outro
const SCRIPT = `
Fourteen percent of South Asians cannot activate clopidogrel, yet they are prescribed it at the same rate as Europeans, where only two percent are affected. This is a measurable health equity gap hiding in plain sight. Meet Anukriti PGx. A pharmacogenomic intelligence superpower that any healthcare agent on Prompt Opinion can invoke, built on M C P, S H A R P, and F H I R.

Here is the Consultant agent in action. We send a real clinical question. A South Asian patient with CYP 2 C 19 star two slash star two needs antiplatelet therapy post P C I. In one point three seven milliseconds, five specialist agents activate. Population reasoning, pharmacogene phenotype inference, knowledge graph traversal, sufficiency governance, and deterministic verification. The response is a full F H I R bundle. A Detected Issue, a Clinical Impression, and a Provenance chain. Every claim is cited. C P I C guideline. Pub Med I Ds. Pharm G K B accession. No hallucinations, no silent prescriptions.

But what if another agent proposes a recommendation, and we need to verify it? The Evidence Reviewer runs six safety checks. Evidence grounding. Deterministic boundary. Provenance. Guideline conflicts. Sparse population data. And hallucination detection. Six out of six pass. Autonomous delivery approved. No human escalation needed. And when evidence is insufficient, the system abstains, citing a specific rule I D.

The Prescriber agent demonstrates composition. Before writing a prescription, it consults the Anukriti P G x Consultant via agent to agent protocol. The prescriber asks, should I proceed with clopidogrel? The consultant responds with alternatives and evidence. The prescriber makes an informed decision. This is agents collaborating, each doing what it does best.

Anukriti P G x. Deterministic. Population aware. Every claim cited. No hallucinations. Built on M C P, S H A R P, and F H I R R five. Available now on the Prompt Opinion marketplace.
`.trim();

console.log("🎤 Generating voiceover via ElevenLabs...");
console.log(`   Voice ID: ${VOICE_ID}`);
console.log(`   Script length: ${SCRIPT.length} chars`);

const outputPath = path.join(rootDir, "public", "audio", "voiceover.mp3");
fs.mkdirSync(path.dirname(outputPath), { recursive: true });

const response = await fetch(
  `https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}`,
  {
    method: "POST",
    headers: {
      "xi-api-key": API_KEY,
      "Content-Type": "application/json",
      Accept: "audio/mpeg",
    },
    body: JSON.stringify({
      text: SCRIPT,
      model_id: "eleven_multilingual_v2",
      voice_settings: {
        stability: 0.5,
        similarity_boost: 0.75,
        style: 0.3,
        use_speaker_boost: true,
      },
    }),
  },
);

if (!response.ok) {
  const errorText = await response.text();
  console.error(`❌ ElevenLabs API error (${response.status}): ${errorText}`);
  process.exit(1);
}

const buffer = Buffer.from(await response.arrayBuffer());
fs.writeFileSync(outputPath, buffer);

console.log(`✅ Voiceover saved: ${outputPath}`);
console.log(`   Size: ${(buffer.length / 1024).toFixed(1)} KB`);
