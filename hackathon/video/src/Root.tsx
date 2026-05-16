import type { CalculateMetadataFunction } from "remotion";
import { Composition, staticFile } from "remotion";
import { DemoVideo, type DemoVideoProps } from "./DemoVideo";
import { getAudioDuration } from "./get-audio-duration";

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

// The transition between every pair of scenes (frames)
export const TRANSITION_FRAMES = 20;

// Scene IDs — order matches the voiceover script
const SCENE_IDS = ["intro", "consultant", "evidence", "prescriber", "outro"] as const;

// Breathing room after each VO ends before the next scene starts.
// Matches SCENE_TAIL_SECONDS in scripts/generate-voiceover.mjs
const TAIL_SEC: Record<string, number> = {
  intro: 1.0,
  consultant: 2.5,
  evidence: 2.0,
  prescriber: 2.0,
  outro: 0.8,
};

const calculateMetadata: CalculateMetadataFunction<DemoVideoProps> = async () => {
  // Measure each voiceover file and derive the scene durations
  const scenes = await Promise.all(
    SCENE_IDS.map(async (id) => {
      const voSrc = staticFile(`voiceover/vo-${id}.mp3`);
      const voSec = await getAudioDuration(voSrc);
      const durationInFrames = Math.ceil((voSec + TAIL_SEC[id]) * FPS);
      return { id, durationInFrames, voDurationInFrames: Math.ceil(voSec * FPS) };
    }),
  );

  // TransitionSeries shortens total duration by transition length per join
  const joins = scenes.length - 1;
  const totalDurationInFrames =
    scenes.reduce((sum, s) => sum + s.durationInFrames, 0) -
    joins * TRANSITION_FRAMES;

  return {
    durationInFrames: totalDurationInFrames,
    props: { scenes },
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="DemoVideo"
      component={DemoVideo}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
      // Default props are a placeholder — calculateMetadata replaces them
      defaultProps={{
        scenes: SCENE_IDS.map((id) => ({
          id,
          durationInFrames: 5 * FPS,
          voDurationInFrames: 5 * FPS,
        })),
      }}
      durationInFrames={30 * FPS}
      calculateMetadata={calculateMetadata}
    />
  );
};
