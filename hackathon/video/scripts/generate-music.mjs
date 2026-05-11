#!/usr/bin/env node
/**
 * Generate instrumental background music via ElevenLabs Music API.
 *
 * Output: public/audio/background.mp3
 *
 * Usage:
 *   export ELEVENLABS_API_KEY=sk_...
 *   node scripts/generate-music.mjs
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

const PROMPT =
  "Uplifting cinematic tech background score. Subtle ambient synth pads, soft arpeggiated piano, gentle electronic percussion building slowly. Inspiring, confident, suitable for a medical AI product demo. Low-energy but forward-moving. No vocals.";

const DURATION_MS = 185000; // 3:05, slightly longer than video so it never cuts early

console.log("🎵 Generating background music via ElevenLabs Music...");
console.log(`   Duration: ${DURATION_MS / 1000}s`);

const response = await fetch("https://api.elevenlabs.io/v1/music", {
  method: "POST",
  headers: {
    "xi-api-key": API_KEY,
    "Content-Type": "application/json",
    Accept: "audio/mpeg",
  },
  body: JSON.stringify({
    prompt: PROMPT,
    music_length_ms: DURATION_MS,
  }),
});

if (!response.ok) {
  const errorText = await response.text();
  console.error(`❌ ElevenLabs Music API error (${response.status}): ${errorText}`);
  console.error(
    "   (Music API may require a paid plan — falling back: drop a royalty-free track at public/audio/background.mp3 manually)",
  );
  process.exit(1);
}

const buffer = Buffer.from(await response.arrayBuffer());
const outputPath = path.join(rootDir, "public", "audio", "background.mp3");
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, buffer);

console.log(`✅ Background music: ${outputPath} (${(buffer.length / 1024 / 1024).toFixed(2)} MB)`);
