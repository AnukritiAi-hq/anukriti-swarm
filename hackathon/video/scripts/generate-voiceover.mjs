#!/usr/bin/env node
/**
 * Generate voiceover + word-level subtitles via ElevenLabs TTS.
 *
 * Outputs:
 *   public/audio/voiceover.mp3
 *   src/subtitles.json          (word-level timing for on-screen captions)
 *
 * Usage:
 *   export ELEVENLABS_API_KEY=sk_...
 *   node scripts/generate-voiceover.mjs
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

const API_KEY = process.env.ELEVENLABS_API_KEY;
if (!API_KEY) {
  console.error("❌ ELEVENLABS_API_KEY env var not set");
  process.exit(1);
}

// Voice: "Adam" — clear, confident, tech-narrator style
// Other good options:
//   21m00Tcm4TlvDq8ikWAM  — Rachel (professional female)
//   TxGEqnHWrfWFTfGW9XjX  — Josh (deep male)
//   pNInz6obpgDQGcFmaJgB  — Adam (confident male)  ← default
const VOICE_ID = process.env.ELEVENLABS_VOICE_ID || "pNInz6obpgDQGcFmaJgB";

// Script broken into timed scenes for subtitle generation.
// Each entry is one scene that maps to DemoVideo.tsx timings.
const SCENES = [
  {
    id: "intro",
    startSec: 0,
    text:
      "Fourteen percent of South Asians cannot activate clopidogrel. Yet they are prescribed it at the same rate as Europeans, where only two percent are affected. Meet Anukriti PGx. A pharmacogenomic intelligence superpower. Built on MCP, SHARP, and FHIR.",
  },
  {
    id: "consultant",
    startSec: 30,
    text:
      "Watch the Consultant agent in action. We ask a real clinical question. In under two milliseconds, five specialist agents collaborate. Population reasoning. Phenotype inference. Knowledge graph traversal. Sufficiency governance. And deterministic verification. The response is a full FHIR bundle. Every claim is cited. CPIC guideline. PubMed PMID. PharmGKB accession. No hallucinations. No silent prescriptions.",
  },
  {
    id: "evidence",
    startSec: 90,
    text:
      "When another agent proposes a recommendation, we verify it. The Evidence Reviewer runs six safety checks. Evidence grounding. Deterministic boundary. Provenance. Guideline conflicts. Sparse population data. Hallucination detection. Six out of six pass. Autonomous delivery approved.",
  },
  {
    id: "prescriber",
    startSec: 135,
    text:
      "The Prescriber Agent demonstrates composition. Before writing a prescription, it consults the Anukriti PGx Consultant via agent-to-agent protocol. The consultant responds with alternatives and evidence. The prescriber makes an informed decision.",
  },
  {
    id: "outro",
    startSec: 165,
    text:
      "Anukriti PGx. Deterministic. Population aware. Every claim cited. No hallucinations. Built on MCP, SHARP, and FHIR R5.",
  },
];

const FULL_SCRIPT = SCENES.map((s) => s.text).join(" ");

console.log("🎤 Generating voiceover via ElevenLabs...");
console.log(`   Voice ID: ${VOICE_ID}`);
console.log(`   Script length: ${FULL_SCRIPT.length} chars`);

const audioOutput = path.join(rootDir, "public", "audio", "voiceover.mp3");
fs.mkdirSync(path.dirname(audioOutput), { recursive: true });

// Use the timestamps endpoint so we get character-level timing for subtitles
const response = await fetch(
  `https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}/with-timestamps`,
  {
    method: "POST",
    headers: {
      "xi-api-key": API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text: FULL_SCRIPT,
      model_id: "eleven_multilingual_v2",
      voice_settings: {
        stability: 0.55,
        similarity_boost: 0.8,
        style: 0.25,
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

const result = await response.json();

// Save audio
const audioBuffer = Buffer.from(result.audio_base64, "base64");
fs.writeFileSync(audioOutput, audioBuffer);
console.log(`✅ Voiceover: ${audioOutput} (${(audioBuffer.length / 1024).toFixed(1)} KB)`);

// Build word-level subtitle data from character timings
const alignment = result.alignment || result.normalized_alignment;
if (!alignment) {
  console.error("⚠️  No alignment data in response — subtitles will be scene-level only");
  process.exit(0);
}

const chars = alignment.characters || [];
const starts = alignment.character_start_times_seconds || [];
const ends = alignment.character_end_times_seconds || [];

// Group characters into words
const words = [];
let current = { text: "", start: 0, end: 0 };
for (let i = 0; i < chars.length; i++) {
  const ch = chars[i];
  if (ch === " " || ch === "\n") {
    if (current.text) {
      words.push({ ...current });
      current = { text: "", start: 0, end: 0 };
    }
  } else {
    if (!current.text) current.start = starts[i];
    current.text += ch;
    current.end = ends[i];
  }
}
if (current.text) words.push(current);

// Group words into subtitle "lines" of 6-8 words for readability
const LINES_TARGET_WORDS = 7;
const lines = [];
let lineBuf = [];
for (const word of words) {
  lineBuf.push(word);
  const endsLine =
    /[.!?]$/.test(word.text) ||
    lineBuf.length >= LINES_TARGET_WORDS ||
    /[,;:]$/.test(word.text) && lineBuf.length >= 4;
  if (endsLine) {
    lines.push({
      text: lineBuf.map((w) => w.text).join(" "),
      startSec: lineBuf[0].start,
      endSec: lineBuf[lineBuf.length - 1].end,
    });
    lineBuf = [];
  }
}
if (lineBuf.length) {
  lines.push({
    text: lineBuf.map((w) => w.text).join(" "),
    startSec: lineBuf[0].start,
    endSec: lineBuf[lineBuf.length - 1].end,
  });
}

const subsOutput = path.join(rootDir, "src", "subtitles.json");
fs.writeFileSync(subsOutput, JSON.stringify(lines, null, 2));
console.log(`✅ Subtitles: ${subsOutput} (${lines.length} lines)`);
console.log(`   Total audio duration: ${ends[ends.length - 1]?.toFixed(1)}s`);
