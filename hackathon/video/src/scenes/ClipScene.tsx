import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadJetBrains } from "@remotion/google-fonts/JetBrainsMono";
import { Video } from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const { fontFamily: inter } = loadInter("normal", {
  weights: ["400", "500", "600", "700", "800"],
  subsets: ["latin"],
});
const { fontFamily: mono } = loadJetBrains("normal", {
  weights: ["400", "500"],
  subsets: ["latin"],
});

const EASE_OUT_EXPO = Easing.bezier(0.16, 1, 0.3, 1);

type Props = {
  title: string;
  subtitle: string;
  clipSrc: string;
  highlight: string;
  accent: string;
  number: string;
};

export const ClipScene: React.FC<Props> = ({
  title,
  subtitle,
  clipSrc,
  highlight,
  accent,
  number,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const headerOpacity = interpolate(frame, [0, 18], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });
  const headerY = interpolate(frame, [0, 18], [-20, 0], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });

  const clipOpacity = interpolate(frame, [12, 35], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });
  const clipScale = interpolate(frame, [12, 35], [0.96, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });

  const highlightOpacity = interpolate(
    frame,
    [Math.max(0, durationInFrames - 90), Math.max(0, durationInFrames - 60)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_OUT_EXPO },
  );
  const highlightY = interpolate(
    frame,
    [Math.max(0, durationInFrames - 90), Math.max(0, durationInFrames - 60)],
    [20, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_OUT_EXPO },
  );

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0a0e1a 0%, #111827 100%)",
        fontFamily: inter,
      }}
    >
      {/* Accent glow */}
      <div
        style={{
          position: "absolute",
          top: "-220px",
          left: "50%",
          transform: "translateX(-50%)",
          width: "1100px",
          height: "650px",
          borderRadius: "50%",
          background: `radial-gradient(ellipse, ${accent}22 0%, transparent 60%)`,
          filter: "blur(40px)",
        }}
      />

      {/* Header */}
      <div
        style={{
          opacity: headerOpacity,
          transform: `translateY(${headerY}px)`,
          padding: "36px 80px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "22px" }}>
          <div
            style={{
              width: "74px",
              height: "74px",
              borderRadius: "18px",
              background: `${accent}20`,
              border: `2px solid ${accent}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "36px",
              fontWeight: 800,
              color: accent,
            }}
          >
            {number}
          </div>
          <div>
            <div
              style={{
                fontSize: "17px",
                color: accent,
                fontWeight: 600,
                letterSpacing: "3px",
                textTransform: "uppercase",
                marginBottom: "4px",
              }}
            >
              Live Demo
            </div>
            <div
              style={{
                fontSize: "50px",
                color: "#ffffff",
                fontWeight: 700,
                letterSpacing: "-1px",
                lineHeight: 1.1,
              }}
            >
              {title}
            </div>
            <div
              style={{
                fontSize: "21px",
                color: "#94a3b8",
                marginTop: "6px",
                fontWeight: 400,
              }}
            >
              {subtitle}
            </div>
          </div>
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: "4px",
          }}
        >
          <div
            style={{
              fontSize: "26px",
              fontWeight: 800,
              color: "#ffffff",
              letterSpacing: "2px",
            }}
          >
            ANUKRITI PGx
          </div>
          <div
            style={{
              fontSize: "13px",
              color: "#64748b",
              letterSpacing: "3px",
            }}
          >
            MCP · SHARP · FHIR
          </div>
        </div>
      </div>

      {/* Video clip framed as a browser */}
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 80px 200px",
          opacity: clipOpacity,
          transform: `scale(${clipScale})`,
        }}
      >
        <div
          style={{
            position: "relative",
            width: "100%",
            height: "100%",
            borderRadius: "18px",
            overflow: "hidden",
            border: `2px solid ${accent}55`,
            boxShadow: `0 40px 100px ${accent}33, 0 0 0 1px rgba(255,255,255,0.04) inset`,
            background: "#000",
          }}
        >
          {/* Browser chrome */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: "34px",
              background: "#1e293b",
              display: "flex",
              alignItems: "center",
              padding: "0 16px",
              gap: "8px",
              zIndex: 2,
              borderBottom: "1px solid rgba(255,255,255,0.05)",
            }}
          >
            <div style={{ display: "flex", gap: "6px" }}>
              <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#ef4444" }} />
              <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#fbbf24" }} />
              <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#22c55e" }} />
            </div>
            <div
              style={{
                flex: 1,
                textAlign: "center",
                fontSize: "12px",
                color: "#94a3b8",
                fontFamily: mono,
              }}
            >
              app.promptopinion.ai
            </div>
            <div style={{ width: "60px" }} />
          </div>

          <Video
            src={staticFile(clipSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              paddingTop: "34px",
              boxSizing: "border-box",
            }}
            muted
            loop
          />
        </div>
      </div>

      {/* Highlight banner */}
      <div
        style={{
          position: "absolute",
          bottom: "60px",
          left: 0,
          right: 0,
          opacity: highlightOpacity,
          transform: `translateY(${highlightY}px)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            background: `linear-gradient(90deg, ${accent}22, ${accent}33, ${accent}22)`,
            border: `2px solid ${accent}`,
            borderRadius: "16px",
            padding: "16px 40px",
            fontSize: "24px",
            color: "#ffffff",
            fontWeight: 600,
            letterSpacing: "0.3px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
            boxShadow: `0 10px 40px ${accent}33`,
          }}
        >
          <span style={{ fontSize: "26px" }}>✓</span>
          {highlight}
        </div>
      </div>
    </AbsoluteFill>
  );
};
