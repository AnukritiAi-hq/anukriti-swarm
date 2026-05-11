import { Composition } from "remotion";
import { DemoVideo } from "./DemoVideo";

// 3 minutes at 30fps = 5400 frames
// Breakdown (frames):
//   Intro:      0 - 900    (0:00-0:30)  30s
//   Consultant: 900 - 2700 (0:30-1:30)  60s
//   Evidence:   2700 - 4050 (1:30-2:15) 45s
//   Prescriber: 4050 - 4950 (2:15-2:45) 30s
//   Outro:      4950 - 5400 (2:45-3:00) 15s
export const TOTAL_FRAMES = 5400;
export const FPS = 30;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="DemoVideo"
        component={DemoVideo}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};
