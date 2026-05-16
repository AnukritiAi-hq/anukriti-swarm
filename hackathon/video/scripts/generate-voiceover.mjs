#!/usr/bin/env node
/**
 * Generate per-scene voiceover + Caption-format JSON via ElevenLabs.
 *
 * Follows the Remotion best-practices voiceover + captions pattern:
 * - One MP3 per scene → each scene auto-sizes via calculateMetadata
 * - One captions.json (Caption[] format) for @remotion/captions
 *
 * Outputs:
 *   public/voiceover/vo-intro.mp3
 *   public/voiceover/vo-consultant.mp3
 *   public/voiceover/vo-evidence.mp3
 *   public/voiceover/vo-prescriber.mp3
 *   public/voiceover/vo-outro.mp3
 *   public/captions.json   (Caption[] format, timed to absolute video timeline)
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

// Adam — confident tech-narrator
const VOICE_ID = process.env.ELEVENLABS_VOICE_ID || "pNInz6obpgDQGcFmaJgB";

// Voice settings tuned for clear, measured delivery
const VOICE_SETTINGS = {
  stability: 0.6,
  similarity_boost: 0.8,
  style: 0.2,
  use_speaker_boost: true,
};

// Scene scripts, ordered. Actual durations are discovered at render time
// via calculateMetadata — we no longer hard-code scene lengths.
const SCENES = [
  {
    id: "intro",
    text:
      "Fourteen percent of South Asians cannot activate clopidogrel. Yet they are prescribed it at the same rate as Europeans, where only two percent are affected. Meet Anukriti PGx. Pharmacogenomic intelligence, as a superpower. Built on MCP, SHARP, and FHIR.",
  },
  {
    id: "consultant",
    text:
      "Watch the Consultant agent in action. We ask a real clinical question. In under two milliseconds, five specialist agents collaborate. Population reasoning. Phenotype inference. Knowledge graph traversal. Sufficiency governance. And deterministic verification. The response is a full FHIR bundle. Every claim is cited. CPIC guideline. PubMed I D. PharmGKB accession. No hallucinations. No silent prescriptions.",
  },
  {
    id: "evidence",
    text:
      "When another agent proposes a recommendation, we verify it. The Evidence Reviewer runs six safety checks. Evidence grounding. Deterministic boundary. Provenance. Guideline conflicts. Sparse population data. Hallucination detection. Six out of six pass. Autonomous delivery approved.",
  },
  {
    id: "prescriber",
    text:
      "The Prescriber agent demonstrates composition. Before writing a prescription, it consults the Anukriti P G x Consultant, via agent to agent protocol. The consultant responds with alternatives and evidence. The prescriber makes an informed decision.",
  },
  {
    id: "outro",
    text:
      "Anukriti P G x. Deterministic. Population aware. Every claim cited. No hallucinations.",
  },
];

// Breathing room we want AFTER each scene's voiceover ends
// (so visuals don't cut the instant the voice stops)
const SCENE_TAIL_SECONDS = {
  intro: 1.0,
  consultant: 2.5, // let the tool call / JSON output breathe
  evidence: 2.0,
  prescriber: 2.0,
  outro: 0.8,
};

const audioDir = path.join(rootDir, "public", "voiceover");
fs.mkdirSync(audioDir, { recursive: true });

// Caption format from @remotion/captions:
// { text, startMs, endMs, timestampMs, confidence }
const allCaptions = [];
const sceneDurations = []; // seconds; used by the Remotion component via captions.json sidecar
let absoluteOffsetSec = 0;

for (const scene of SCENES) {
  console.log(`🎤 ${scene.id} (${scene.text.length} chars)...`);

  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}/with-timestamps`,
    {
      method: "POST",
      headers: {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: scene.text,
        model_id: "eleven_multilingual_v2",
        voice_settings: VOICE_SETTINGS,
      }),
    },
  );

  if (!response.ok) {
    const errorText = await response.text();
    console.error(`❌ ${scene.id}: ${response.status} ${errorText}`);
    process.exit(1);
  }

  const result = await response.json();

  // Save audio
  const audioBuffer = Buffer.from(result.audio_base64, "base64");
  const audioPath = path.join(audioDir, `vo-${scene.id}.mp3`);
  fs.writeFileSync(audioPath, audioBuffer);

  // Extract word timings from character alignment
  const alignment = result.alignment || result.normalized_alignment;
  const chars = alignment?.characters || [];
  const starts = alignment?.character_start_times_seconds || [];
  const ends = alignment?.character_end_times_seconds || [];

  const vDurSec = ends[ends.length - 1] || 0;

  // Build word-level tokens (Caption format expects one Caption per word)
  let current = { text: "", start: 0, end: 0 };
  for (let i = 0; i < chars.length; i++) {
    const ch = chars[i];
    if (ch === " " || ch === "\n") {
      if (current.text) {
        allCaptions.push(captionFromWord(current, absoluteOffsetSec));
        current = { text: "", start: 0, end: 0 };
      }
    } else {
      if (!current.text) current.start = starts[i];
      current.text += ch;
      current.end = ends[i];
    }
  }
  if (current.text) {
    allCaptions.push(captionFromWord(current, absoluteOffsetSec));
  }

  const totalSceneSec = vDurSec + SCENE_TAIL_SECONDS[scene.id];
  sceneDurations.push({
    id: scene.id,
    durationSec: totalSceneSec,
    voiceDurationSec: vDurSec,
  });

  console.log(
    `   ✓ vo-${scene.id}.mp3 (voice: ${vDurSec.toFixed(1)}s, scene: ${totalSceneSec.toFixed(1)}s)`,
  );

  absoluteOffsetSec += totalSceneSec;
}

// Write Caption[] + scene meta as sidecars Remotion will fetch at render time
const captionsOutput = path.join(rootDir, "public", "captions.json");
fs.writeFileSync(captionsOutput, JSON.stringify(allCaptions, null, 2));

const metaOutput = path.join(rootDir, "public", "scene-meta.json");
fs.writeFileSync(metaOutput, JSON.stringify(sceneDurations, null, 2));

console.log(`\n✅ ${allCaptions.length} captions → public/captions.json`);
console.log(`✅ ${sceneDurations.length} scenes → public/scene-meta.json`);
console.log(`✅ Total video: ${absoluteOffsetSec.toFixed(1)}s`);

// ---------------------------------------------------------------------------

function captionFromWord(word, absoluteOffsetSec) {
  // Whitespace-sensitive: prefix a space before the word (except first-of-scene)
  const text = " " + word.text;
  const startMs = Math.round((absoluteOffsetSec + word.start) * 1000);
  const endMs = Math.round((absoluteOffsetSec + word.end) * 1000);
  return {
    text,
    startMs,
    endMs,
    timestampMs: (startMs + endMs) / 2,
    confidence: 1,
  };
}
