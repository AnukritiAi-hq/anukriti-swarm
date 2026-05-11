#!/usr/bin/env node
/**
 * Generate per-scene voiceover files + subtitle data via ElevenLabs.
 *
 * Each scene gets its own audio file so it plays when that scene is on
 * screen, perfectly synced — no drift from the video timeline.
 *
 * Outputs:
 *   public/audio/vo-intro.mp3
 *   public/audio/vo-consultant.mp3
 *   public/audio/vo-evidence.mp3
 *   public/audio/vo-prescriber.mp3
 *   public/audio/vo-outro.mp3
 *   src/subtitles.json              (all scenes merged with absolute timing)
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

// Each scene's script is tuned to fit inside its time window with a small buffer.
// Scene window durations (seconds):
//   intro:      30s
//   consultant: 60s  → 58s of clip
//   evidence:   45s  → 40s of clip
//   prescriber: 30s  → 25s of clip
//   outro:      15s
//
// The VO lengths below aim for ~70-80% of the scene window to leave
// breathing room at scene start + end.
//
// Absolute start times (seconds into the full video) — these must match
// the Sequence `from` values in DemoVideo.tsx divided by fps (30).
const SCENES = [
  {
    id: "intro",
    absoluteStartSec: 0,
    text:
      "Fourteen percent of South Asians cannot activate clopidogrel. Yet they are prescribed it at the same rate as Europeans, where only two percent are affected. Meet Anukriti PGx. Pharmacogenomic intelligence, as a superpower. Built on MCP, SHARP, and FHIR.",
  },
  {
    id: "consultant",
    absoluteStartSec: 30,
    text:
      "Watch the Consultant agent in action. We ask a real clinical question. In under two milliseconds, five specialist agents collaborate. Population reasoning. Phenotype inference. Knowledge graph traversal. Sufficiency governance. And deterministic verification. The response is a full FHIR bundle. Every claim is cited. CPIC guideline. PubMed I D. PharmGKB accession. No hallucinations. No silent prescriptions.",
  },
  {
    id: "evidence",
    absoluteStartSec: 90,
    text:
      "When another agent proposes a recommendation, we verify it. The Evidence Reviewer runs six safety checks. Evidence grounding. Deterministic boundary. Provenance. Guideline conflicts. Sparse population data. Hallucination detection. Six out of six pass. Autonomous delivery approved.",
  },
  {
    id: "prescriber",
    absoluteStartSec: 135,
    text:
      "The Prescriber agent demonstrates composition. Before writing a prescription, it consults the Anukriti P G x Consultant, via agent to agent protocol. The consultant responds with alternatives and evidence. The prescriber makes an informed decision.",
  },
  {
    id: "outro",
    absoluteStartSec: 165,
    text:
      "Anukriti P G x. Deterministic. Population aware. Every claim cited. No hallucinations.",
  },
];

// Pacing that fills the scene without rushing.
// ElevenLabs doesn't accept speed directly, but we control pacing via voice_settings.style
const VOICE_SETTINGS = {
  stability: 0.6,
  similarity_boost: 0.8,
  style: 0.2,
  use_speaker_boost: true,
};

const audioDir = path.join(rootDir, "public", "audio");
fs.mkdirSync(audioDir, { recursive: true });

const allSubtitles = [];

for (const scene of SCENES) {
  console.log(`🎤 Generating VO: ${scene.id} (${scene.text.length} chars)...`);

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

  // Save per-scene audio file
  const audioBuffer = Buffer.from(result.audio_base64, "base64");
  const audioPath = path.join(audioDir, `vo-${scene.id}.mp3`);
  fs.writeFileSync(audioPath, audioBuffer);

  // Extract word-level subtitles for this scene
  const alignment = result.alignment || result.normalized_alignment;
  const chars = alignment?.characters || [];
  const starts = alignment?.character_start_times_seconds || [];
  const ends = alignment?.character_end_times_seconds || [];

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

  // Group words into ~6-word subtitle lines, breaking on punctuation
  const lines = [];
  let lineBuf = [];
  for (const word of words) {
    lineBuf.push(word);
    const endsLine =
      /[.!?]$/.test(word.text) ||
      lineBuf.length >= 7 ||
      (/[,;:]$/.test(word.text) && lineBuf.length >= 4);
    if (endsLine) {
      lines.push({
        text: lineBuf.map((w) => w.text).join(" "),
        // Shift to absolute timeline
        startSec: lineBuf[0].start + scene.absoluteStartSec,
        endSec: lineBuf[lineBuf.length - 1].end + scene.absoluteStartSec,
      });
      lineBuf = [];
    }
  }
  if (lineBuf.length) {
    lines.push({
      text: lineBuf.map((w) => w.text).join(" "),
      startSec: lineBuf[0].start + scene.absoluteStartSec,
      endSec: lineBuf[lineBuf.length - 1].end + scene.absoluteStartSec,
    });
  }
  allSubtitles.push(...lines);

  const vDur = ends[ends.length - 1] || 0;
  console.log(
    `   ✓ ${audioPath.replace(rootDir + "/", "")} (${vDur.toFixed(1)}s, ${lines.length} sub lines, starts at ${scene.absoluteStartSec}s)`,
  );
}

// Write the merged subtitle file
const subsOutput = path.join(rootDir, "src", "subtitles.json");
fs.writeFileSync(subsOutput, JSON.stringify(allSubtitles, null, 2));
console.log(`\n✅ Subtitles: ${subsOutput} (${allSubtitles.length} lines total)`);
console.log(`✅ Voiceovers generated per-scene — each starts when its scene starts.`);
