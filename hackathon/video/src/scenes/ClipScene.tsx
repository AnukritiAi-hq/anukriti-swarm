import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type Props = {
  title: string;
  subtitle: string;
  clipSrc: string;
  highlightText: string;
  accent: string;
};

export const ClipScene: React.FC<Props> = ({
  title,
  subtitle,
  clipSrc,
  highlightText,
  accent,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const headerOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  const clipOpacity = interpolate(frame, [20, 40], [0, 1], {
    extrapolateRight: "clamp",
  });

  const highlightOpacity = interpolate(
    frame,
    [durationInFrames - 90, durationInFrames - 60],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0a0e1a 0%, #111827 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top header bar */}
      <div
        style={{
          opacity: headerOpacity,
          padding: "40px 80px 20px 80px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div>
          <div
            style={{
              fontSize: "20px",
              color: accent,
              fontWeight: 600,
              letterSpacing: "3px",
              textTransform: "uppercase",
              marginBottom: "8px",
            }}
          >
            Live Demo
          </div>
          <div
            style={{
              fontSize: "52px",
              color: "#ffffff",
              fontWeight: 700,
              letterSpacing: "-1px",
            }}
          >
            {title}
          </div>
          <div
            style={{
              fontSize: "22px",
              color: "#94a3b8",
              marginTop: "8px",
            }}
          >
            {subtitle}
          </div>
        </div>
        <div
          style={{
            fontSize: "28px",
            fontWeight: 700,
            color: "#ffffff",
            opacity: 0.5,
            letterSpacing: "2px",
          }}
        >
          ANUKRITI PGx
        </div>
      </div>

      {/* Video clip — centered, rounded border */}
      <div
        style={{
          opacity: clipOpacity,
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 80px 20px 80px",
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            borderRadius: "24px",
            overflow: "hidden",
            border: `3px solid ${accent}33`,
            boxShadow: `0 40px 80px ${accent}22`,
            background: "#000",
          }}
        >
          <OffthreadVideo
            src={staticFile(clipSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
            }}
            // Mute the clip — we have our own voiceover
            muted
          />
        </div>
      </div>

      {/* Bottom highlight banner */}
      <div
        style={{
          opacity: highlightOpacity,
          padding: "20px 80px 40px 80px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            background: `${accent}22`,
            border: `2px solid ${accent}`,
            borderRadius: "16px",
            padding: "16px 40px",
            fontSize: "26px",
            color: "#ffffff",
            fontWeight: 600,
            letterSpacing: "0.5px",
          }}
        >
          ✓ {highlightText}
        </div>
      </div>
    </AbsoluteFill>
  );
};
