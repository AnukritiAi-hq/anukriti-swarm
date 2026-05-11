import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const titleSpring = spring({
    frame: frame - 5,
    fps,
    config: { damping: 14, stiffness: 90 },
  });

  const subtitleSpring = spring({
    frame: frame - 35,
    fps,
    config: { damping: 18, stiffness: 100 },
  });

  const fadeOut = interpolate(
    frame,
    [durationInFrames - 15, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const pillars = [
    { icon: "🎯", text: "Deterministic", accent: "#60a5fa" },
    { icon: "🌍", text: "Population-aware", accent: "#34d399" },
    { icon: "📚", text: "Every claim cited", accent: "#fbbf24" },
    { icon: "🛡️", text: "No hallucinations", accent: "#f472b6" },
  ];

  const bgRotate = (frame * 0.5) % 360;

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at center, #1e1b4b 0%, #0a0e1a 60%, #000000 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px",
        overflow: "hidden",
        opacity: fadeOut,
      }}
    >
      {/* Rotating background accent */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          width: "1400px",
          height: "1400px",
          transform: `translate(-50%, -50%) rotate(${bgRotate}deg)`,
          background:
            "conic-gradient(from 0deg, transparent, rgba(96,165,250,0.06), transparent, rgba(236,72,153,0.06), transparent)",
        }}
      />

      {/* Title */}
      <div
        style={{
          transform: `scale(${0.85 + titleSpring * 0.15})`,
          opacity: titleSpring,
          textAlign: "center",
          zIndex: 1,
        }}
      >
        <div
          style={{
            fontSize: "110px",
            fontWeight: 800,
            background: "linear-gradient(180deg, #ffffff 0%, #94a3b8 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            letterSpacing: "-3px",
            marginBottom: "16px",
          }}
        >
          Anukriti PGx
        </div>
        <div
          style={{
            fontSize: "28px",
            color: "#94a3b8",
            letterSpacing: "4px",
            textTransform: "uppercase",
          }}
        >
          Built on MCP · SHARP · FHIR R5
        </div>
      </div>

      {/* Pillars */}
      <div
        style={{
          opacity: subtitleSpring,
          transform: `translateY(${(1 - subtitleSpring) * 30}px)`,
          display: "flex",
          gap: "32px",
          marginTop: "80px",
          zIndex: 1,
        }}
      >
        {pillars.map((p, i) => {
          const pillarSpring = spring({
            frame: frame - (50 + i * 8),
            fps,
            config: { damping: 14, stiffness: 100 },
          });
          return (
            <div
              key={p.text}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: `1px solid ${p.accent}44`,
                borderRadius: "16px",
                padding: "28px 36px",
                textAlign: "center",
                minWidth: "240px",
                opacity: pillarSpring,
                transform: `translateY(${(1 - pillarSpring) * 40}px) scale(${0.9 + pillarSpring * 0.1})`,
                boxShadow: `0 10px 40px ${p.accent}22`,
              }}
            >
              <div style={{ fontSize: "52px", marginBottom: "12px" }}>
                {p.icon}
              </div>
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
          opacity: spring({
            frame: frame - 180,
            fps,
            config: { damping: 18, stiffness: 100 },
          }),
          marginTop: "80px",
          textAlign: "center",
          zIndex: 1,
        }}
      >
        <div
          style={{
            display: "inline-block",
            padding: "16px 32px",
            background: "rgba(96,165,250,0.1)",
            border: "1px solid rgba(96,165,250,0.4)",
            borderRadius: "100px",
            fontSize: "24px",
            color: "#93c5fd",
            fontFamily: "monospace",
            marginBottom: "16px",
          }}
        >
          github.com/AnukritiAi-hq/anukriti-swarm
        </div>
        <div
          style={{
            fontSize: "18px",
            color: "#64748b",
            letterSpacing: "2px",
          }}
        >
          AGENTS ASSEMBLE 2026 · PROMPT OPINION
        </div>
      </div>
    </AbsoluteFill>
  );
};
