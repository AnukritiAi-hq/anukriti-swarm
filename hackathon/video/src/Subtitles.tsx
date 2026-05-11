import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import subtitles from "./subtitles.json";

type SubtitleLine = {
  text: string;
  startSec: number;
  endSec: number;
};

const SUBS = subtitles as SubtitleLine[];

export const Subtitles: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentSec = frame / fps;

  const active = SUBS.find(
    (s) => currentSec >= s.startSec && currentSec <= s.endSec + 0.15,
  );

  if (!active) return null;

  // Progress within the subtitle for subtle reveal animation
  const lineDuration = active.endSec - active.startSec;
  const progress = Math.min(
    1,
    Math.max(0, (currentSec - active.startSec) / Math.max(lineDuration, 0.2)),
  );
  const opacity = progress < 0.1 ? progress * 10 : progress > 0.9 ? (1 - progress) * 10 + 0.1 : 1;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        padding: "0 0 60px 0",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          background: "rgba(0, 0, 0, 0.82)",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          backdropFilter: "blur(8px)",
          borderRadius: "12px",
          padding: "16px 32px",
          maxWidth: "1400px",
          textAlign: "center",
          opacity,
          transform: `translateY(${(1 - Math.min(progress * 10, 1)) * 20}px)`,
        }}
      >
        <div
          style={{
            fontSize: "34px",
            color: "#ffffff",
            fontWeight: 500,
            letterSpacing: "0.3px",
            lineHeight: 1.3,
            fontFamily: "system-ui, -apple-system, sans-serif",
            textShadow: "0 2px 8px rgba(0,0,0,0.5)",
          }}
        >
          {active.text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
