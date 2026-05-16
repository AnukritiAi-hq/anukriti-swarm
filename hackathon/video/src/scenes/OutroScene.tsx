import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const { fontFamily: inter } = loadInter("normal", {
  weights: ["400", "500", "700", "800"],
  subsets: ["latin"],
});
const { fontFamily: mono } = loadMono("normal", {
  weights: ["400"],
  subsets: ["latin"],
});

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

const PILLARS = [
  { icon: "🎯", text: "Deterministic", accent: "#60a5fa" },
  { icon: "🌍", text: "Population-aware", accent: "#34d399" },
  { icon: "📚", text: "Every claim cited", accent: "#fbbf24" },
  { icon: "🛡️", text: "No hallucinations", accent: "#f472b6" },
];

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT,
  });
  const titleScale = interpolate(frame, [0, 20], [0.92, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT,
  });

  const linksOpacity = interpolate(frame, [90, 115], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT,
  });

  const bgRotate = (frame * 0.4) % 360;

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at center, #1e1b4b 0%, #0a0e1a 60%, #000000 100%)",
        fontFamily: inter,
        alignItems: "center",
        justifyContent: "center",
        padding: "80px",
        overflow: "hidden",
      }}
    >
      {/* Rotating conic gradient background */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          width: "1400px",
          height: "1400px",
          transform: `translate(-50%, -50%) rotate(${bgRotate}deg)`,
          background:
            "conic-gradient(from 0deg, transparent, rgba(96,165,250,0.08), transparent, rgba(236,72,153,0.08), transparent)",
        }}
      />

      {/* Title */}
      <div
        style={{
          transform: `scale(${titleScale})`,
          opacity: titleOpacity,
          textAlign: "center",
          zIndex: 1,
        }}
      >
        <div
          style={{
            fontSize: "112px",
            fontWeight: 800,
            background: "linear-gradient(180deg, #ffffff 0%, #94a3b8 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            letterSpacing: "-3px",
            marginBottom: "14px",
            lineHeight: 1,
          }}
        >
          Anukriti PGx
        </div>
        <div
          style={{
            fontSize: "26px",
            color: "#94a3b8",
            letterSpacing: "4px",
            textTransform: "uppercase",
            fontWeight: 500,
          }}
        >
          Built on MCP · SHARP · FHIR R5
        </div>
      </div>

      {/* Pillars — staggered reveal */}
      <div
        style={{
          display: "flex",
          gap: "28px",
          marginTop: "70px",
          zIndex: 1,
        }}
      >
        {PILLARS.map((p, i) => {
          const pillarFrame = frame - (30 + i * 6);
          const pillarOpacity = interpolate(pillarFrame, [0, 18], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: EASE_OUT,
          });
          const pillarY = interpolate(pillarFrame, [0, 18], [30, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: EASE_OUT,
          });
          return (
            <div
              key={p.text}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: `1px solid ${p.accent}44`,
                borderRadius: "16px",
                padding: "26px 32px",
                textAlign: "center",
                minWidth: "230px",
                opacity: pillarOpacity,
                transform: `translateY(${pillarY}px)`,
                boxShadow: `0 10px 40px ${p.accent}22`,
              }}
            >
              <div style={{ fontSize: "50px", marginBottom: "10px" }}>{p.icon}</div>
              <div
                style={{
                  fontSize: "22px",
                  color: "#ffffff",
                  fontWeight: 600,
                }}
              >
                {p.text}
              </div>
            </div>
          );
        })}
      </div>

      {/* Links */}
      <div
        style={{
          opacity: linksOpacity,
          marginTop: "70px",
          textAlign: "center",
          zIndex: 1,
        }}
      >
        <div
          style={{
            display: "inline-block",
            padding: "14px 30px",
            background: "rgba(96,165,250,0.1)",
            border: "1px solid rgba(96,165,250,0.4)",
            borderRadius: "100px",
            fontSize: "22px",
            color: "#93c5fd",
            fontFamily: mono,
            marginBottom: "14px",
          }}
        >
          github.com/AnukritiAi-hq/anukriti-swarm
        </div>
        <div
          style={{
            fontSize: "17px",
            color: "#64748b",
            letterSpacing: "2px",
            fontWeight: 500,
          }}
        >
          AGENTS ASSEMBLE 2026 · PROMPT OPINION
        </div>
      </div>
    </AbsoluteFill>
  );
};
