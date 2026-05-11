import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    frame: frame - 10,
    fps,
    config: { damping: 12, stiffness: 100 },
  });

  const subtitleOpacity = interpolate(frame, [60, 90], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const statOpacity = interpolate(frame, [180, 220], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const taglineOpacity = interpolate(frame, [450, 500], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0a0e1a 0%, #1e1b4b 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px",
      }}
    >
      {/* DNA helix accent */}
      <div
        style={{
          position: "absolute",
          top: "10%",
          right: "10%",
          fontSize: "200px",
          opacity: 0.04,
          transform: `rotate(${frame * 0.3}deg)`,
        }}
      >
        🧬
      </div>

      <div
        style={{
          transform: `translateY(${(1 - titleSpring) * 40}px) scale(${
            0.9 + titleSpring * 0.1
          })`,
          opacity: titleSpring,
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontSize: "120px",
            fontWeight: 800,
            color: "#ffffff",
            letterSpacing: "-3px",
            marginBottom: "20px",
          }}
        >
          Anukriti PGx
        </div>
        <div
          style={{
            fontSize: "36px",
            fontWeight: 400,
            color: "#94a3b8",
            letterSpacing: "2px",
          }}
        >
          Pharmacogenomic Intelligence as a Superpower
        </div>
      </div>

      <div
        style={{
          marginTop: "80px",
          opacity: subtitleOpacity,
          fontSize: "28px",
          color: "#cbd5e1",
          textAlign: "center",
          maxWidth: "1200px",
          lineHeight: 1.5,
        }}
      >
        A clinical reality hiding in plain sight:
      </div>

      <div
        style={{
          marginTop: "40px",
          opacity: statOpacity,
          fontSize: "64px",
          fontWeight: 700,
          color: "#fbbf24",
          textAlign: "center",
          lineHeight: 1.2,
        }}
      >
        14% of South Asians
        <div style={{ fontSize: "38px", color: "#e2e8f0", marginTop: "12px" }}>
          cannot activate clopidogrel.
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: "80px",
          opacity: taglineOpacity,
          fontSize: "32px",
          color: "#60a5fa",
          fontWeight: 500,
          textAlign: "center",
        }}
      >
        Current systems ignore ancestry. We fix that.
      </div>
    </AbsoluteFill>
  );
};
