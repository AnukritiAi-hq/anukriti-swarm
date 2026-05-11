import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { IntroScene } from "./scenes/IntroScene";
import { ClipScene } from "./scenes/ClipScene";
import { OutroScene } from "./scenes/OutroScene";

// Scene timings (frames @ 30fps)
const INTRO_START = 0;
const INTRO_DURATION = 900; // 30s

const CONSULTANT_START = 900;
const CONSULTANT_DURATION = 1800; // 60s

const EVIDENCE_START = 2700;
const EVIDENCE_DURATION = 1350; // 45s

const PRESCRIBER_START = 4050;
const PRESCRIBER_DURATION = 900; // 30s

const OUTRO_START = 4950;
const OUTRO_DURATION = 450; // 15s

export const DemoVideo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0a0e1a" }}>
      {/* Background music — soft, low volume */}
      <Audio src={staticFile("audio/background.mp3")} volume={0.12} />

      {/* Voiceover track — full video length */}
      <Audio src={staticFile("audio/voiceover.mp3")} volume={1} />

      {/* Scene 1: Intro (0:00-0:30) */}
      <Sequence from={INTRO_START} durationInFrames={INTRO_DURATION}>
        <IntroScene />
      </Sequence>

      {/* Scene 2: Consultant clip (0:30-1:30) */}
      <Sequence from={CONSULTANT_START} durationInFrames={CONSULTANT_DURATION}>
        <ClipScene
          title="Anukriti PGx Consultant"
          subtitle="FHIR in → DetectedIssue + ClinicalImpression + Provenance out"
          clipSrc="clips/consultant.mp4"
          highlightText="1.37ms end-to-end · 5 agents activated · 4 citations"
          accent="#60a5fa"
        />
      </Sequence>

      {/* Scene 3: Evidence Reviewer clip (1:30-2:15) */}
      <Sequence from={EVIDENCE_START} durationInFrames={EVIDENCE_DURATION}>
        <ClipScene
          title="Evidence Reviewer"
          subtitle="6 safety checks · evidence grounding · bias detection"
          clipSrc="clips/evidence.mp4"
          highlightText="6/6 PASS · autonomous delivery · no escalation"
          accent="#34d399"
        />
      </Sequence>

      {/* Scene 4: Prescriber Agent clip (2:15-2:45) */}
      <Sequence from={PRESCRIBER_START} durationInFrames={PRESCRIBER_DURATION}>
        <ClipScene
          title="Prescriber Agent"
          subtitle="A2A composition · multi-agent workflow"
          clipSrc="clips/prescriber.mp4"
          highlightText="Agent-to-Agent collaboration via MCP"
          accent="#f472b6"
        />
      </Sequence>

      {/* Scene 5: Outro (2:45-3:00) */}
      <Sequence from={OUTRO_START} durationInFrames={OUTRO_DURATION}>
        <OutroScene />
      </Sequence>
    </AbsoluteFill>
  );
};
