import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { IntroScene } from "./scenes/IntroScene";
import { ClipScene } from "./scenes/ClipScene";
import { OutroScene } from "./scenes/OutroScene";
import { Subtitles } from "./Subtitles";

// Scene timings (frames @ 30fps) = seconds shown in comments
// Total: 5400 frames = 3:00
const INTRO_START = 0;
const INTRO_DURATION = 900; // 0:00 – 0:30

const CONSULTANT_START = 900;
const CONSULTANT_DURATION = 1800; // 0:30 – 1:30 (60s, our clip is 58s)

const EVIDENCE_START = 2700;
const EVIDENCE_DURATION = 1350; // 1:30 – 2:15 (45s, our clip is 40s)

const PRESCRIBER_START = 4050;
const PRESCRIBER_DURATION = 900; // 2:15 – 2:45 (30s, our clip is 25s)

const OUTRO_START = 4950;
const OUTRO_DURATION = 450; // 2:45 – 3:00 (15s)

export const DemoVideo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Background music — soft, ducks under voiceover */}
      <Audio src={staticFile("audio/background.mp3")} volume={0.1} />

      {/* Voiceover track — full video length */}
      <Audio src={staticFile("audio/voiceover.mp3")} volume={1} />

      {/* Scene 1: Intro (0:00 – 0:30) */}
      <Sequence from={INTRO_START} durationInFrames={INTRO_DURATION}>
        <IntroScene />
      </Sequence>

      {/* Scene 2: Consultant clip (0:30 – 1:30) */}
      <Sequence from={CONSULTANT_START} durationInFrames={CONSULTANT_DURATION}>
        <ClipScene
          sceneNumber="1"
          title="PGx Consultant"
          subtitle="Real clinical question → FHIR-native answer in 1.37ms"
          clipSrc="clips/consultant.mp4"
          highlightText="5 agents activated · 4 citations · DetectedIssue + Provenance"
          accent="#60a5fa"
        />
      </Sequence>

      {/* Scene 3: Evidence Reviewer clip (1:30 – 2:15) */}
      <Sequence from={EVIDENCE_START} durationInFrames={EVIDENCE_DURATION}>
        <ClipScene
          sceneNumber="2"
          title="Evidence Reviewer"
          subtitle="6 safety checks · evidence grounding · bias detection"
          clipSrc="clips/evidence.mp4"
          highlightText="6/6 PASS · Autonomous delivery · No escalation"
          accent="#34d399"
        />
      </Sequence>

      {/* Scene 4: Prescriber Agent clip (2:15 – 2:45) */}
      <Sequence from={PRESCRIBER_START} durationInFrames={PRESCRIBER_DURATION}>
        <ClipScene
          sceneNumber="3"
          title="Prescriber Agent"
          subtitle="A2A composition · agents consulting agents"
          clipSrc="clips/prescribe.mp4"
          highlightText="Agent-to-Agent via MCP · Multi-agent collaboration"
          accent="#f472b6"
        />
      </Sequence>

      {/* Scene 5: Outro (2:45 – 3:00) */}
      <Sequence from={OUTRO_START} durationInFrames={OUTRO_DURATION}>
        <OutroScene />
      </Sequence>

      {/* Subtitle overlay — sits above everything, reads from src/subtitles.json */}
      <Subtitles />
    </AbsoluteFill>
  );
};
