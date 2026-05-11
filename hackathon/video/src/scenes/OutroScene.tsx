import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame: frame - 5,
    fps,
    config: { damping: 12, stiffness: 100 },
  });

  const pillarsOpacity = interpolate(frame, [60, 120], [0, 1], {
    extrapolateRight: "clamp",
  });

  const linksOpacity = interpolate(frame, [240, 300], [0, 1], {
    extrapolateRight: "clamp",
  });

  const pillars = [
    { icon: "🎯", text: "Deterministic" },
    { icon: "🌍", text: "Population-aware" },
    { icon: "📚", text: "Every claim cited" },
    { icon: "🛡️", text: "No hallucinations" },
  ];

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #1e1b4b 0%, #0a0e1a 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px",
      }}
    >
      <div
        style={{
          transform: `scale(${0.9 + titleSpring * 0.1})`,
          opacity: titleSpring,
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontSize: "84px",
            fontWeight: 800,
            color: "#ffffff",
            letterSpacing: "-2px",
            marginBottom: "16px",
          }}
        >
          Anukriti PGx
        </div>
        <div
          style={{
            fontSize: "28px",
            color: "#94a3b8",
            letterSpacing: "1px",
          }}
        >
          Built on MCP · SHARP · FHIR R5
        </div>
      </div>

      <div
        style={{
          opacity: pillarsOpacity,
          display: "flex",
          gap: "40px",
          marginTop: "80px",
        }}
      >
        {pillars.map((p) => (
          <div
            key={p.text}
            style={{
              background: "#ffffff0a",
              border: "1px solid #ffffff22",
              borderRadius: "16px",
              padding: "24px 32px",
              textAlign: "center",
              minWidth: "220px",
            }}
          >
            <div style={{ fontSize: "48px", marginBottom: "12px" }}>{p.icon}</div>
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
        ))}
      </div>

      <div
        style={{
          opacity: linksOpacity,
          marginTop: "80px",
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontSize: "24px",
            color: "#60a5fa",
            marginBottom: "12px",
          }}
        >
          github.com/AnukritiAi-hq/anukriti-swarm
        </div>
        <div style={{ fontSize: "20px", color: "#64748b" }}>
          Agents Assemble 2026 · Prompt Opinion
        </div>
      </div>
    </AbsoluteFill>
  );
};
