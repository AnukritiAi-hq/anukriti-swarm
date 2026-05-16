import { Audio } from "@remotion/media";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { AbsoluteFill, staticFile } from "remotion";
import { Captions } from "./Subtitles";
import { TRANSITION_FRAMES } from "./Root";
import { ClipScene } from "./scenes/ClipScene";
import { IntroScene } from "./scenes/IntroScene";
import { OutroScene } from "./scenes/OutroScene";

export type SceneMeta = {
  id: "intro" | "consultant" | "evidence" | "prescriber" | "outro";
  durationInFrames: number;
  voDurationInFrames: number;
};

export type DemoVideoProps = {
  scenes: SceneMeta[];
};

const SCENE_CONFIG = {
  consultant: {
    title: "PGx Consultant",
    subtitle: "Real clinical question → FHIR-native answer in 1.37ms",
    clipSrc: "clips/consultant.mp4",
    highlight: "5 agents · 4 citations · DetectedIssue + Provenance",
    accent: "#60a5fa",
    number: "1",
  },
  evidence: {
    title: "Evidence Reviewer",
    subtitle: "6 safety checks · evidence grounding · bias detection",
    clipSrc: "clips/evidence.mp4",
    highlight: "6/6 PASS · Autonomous delivery · No escalation",
    accent: "#34d399",
    number: "2",
  },
  prescriber: {
    title: "Prescriber Agent",
    subtitle: "A2A composition · agents consulting agents",
    clipSrc: "clips/prescribe.mp4",
    highlight: "Agent-to-Agent via MCP · Multi-agent collaboration",
    accent: "#f472b6",
    number: "3",
  },
} as const;

const timing = linearTiming({ durationInFrames: TRANSITION_FRAMES });

export const DemoVideo: React.FC<DemoVideoProps> = ({ scenes }) => {
  // Cumulative frame offsets for absolute audio positioning
  const sceneStarts = scenes.reduce<number[]>((acc, s, i) => {
    const prev = acc[i - 1] ?? 0;
    // Subtract one transition per join (after the first scene)
    const offset = i === 0 ? 0 : prev + scenes[i - 1].durationInFrames - TRANSITION_FRAMES;
    acc.push(offset);
    return acc;
  }, []);

  const byId = Object.fromEntries(scenes.map((s, i) => [s.id, { scene: s, start: sceneStarts[i] }]));

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Background music — loops full video */}
      <Audio src={staticFile("audio/background.mp3")} volume={0.07} />

      {/* Per-scene voiceovers — positioned at absolute scene starts */}
      {scenes.map(({ id }) => (
        <VoiceoverAt key={id} id={id} startFrame={byId[id].start} />
      ))}

      {/* Scenes with fade transitions between each */}
      <TransitionSeries>
        {/* Intro */}
        <TransitionSeries.Sequence durationInFrames={byId.intro.scene.durationInFrames}>
          <IntroScene />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />

        {/* Consultant */}
        <TransitionSeries.Sequence durationInFrames={byId.consultant.scene.durationInFrames}>
          <ClipScene {...SCENE_CONFIG.consultant} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />

        {/* Evidence */}
        <TransitionSeries.Sequence durationInFrames={byId.evidence.scene.durationInFrames}>
          <ClipScene {...SCENE_CONFIG.evidence} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />

        {/* Prescriber */}
        <TransitionSeries.Sequence durationInFrames={byId.prescriber.scene.durationInFrames}>
          <ClipScene {...SCENE_CONFIG.prescriber} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />

        {/* Outro */}
        <TransitionSeries.Sequence durationInFrames={byId.outro.scene.durationInFrames}>
          <OutroScene />
        </TransitionSeries.Sequence>
      </TransitionSeries>

      {/* Captions overlay — reads public/captions.json */}
      <Captions />
    </AbsoluteFill>
  );
};

// Helper component: render a voiceover track at an absolute frame offset
const VoiceoverAt: React.FC<{ id: SceneMeta["id"]; startFrame: number }> = ({ id, startFrame }) => {
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <VoAtOffset id={id} from={startFrame} />
    </AbsoluteFill>
  );
};

// Using Remotion Sequence to delay the audio start
import { Sequence } from "remotion";
const VoAtOffset: React.FC<{ id: SceneMeta["id"]; from: number }> = ({ id, from }) => (
  <Sequence from={from}>
    <Audio src={staticFile(`voiceover/vo-${id}.mp3`)} volume={1} />
  </Sequence>
);
