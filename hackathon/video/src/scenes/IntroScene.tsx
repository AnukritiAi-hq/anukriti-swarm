import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const titleSpring = spring({
    frame: frame - 15,
    fps,
    config: { damping: 14, stiffness: 90 },
  });

  const subtitleSpring = spring({
    frame: frame - 60,
    fps,
    config: { damping: 18, stiffness: 100 },
  });

  const statSpring = spring({
    frame: frame - 180,
    fps,
    config: { damping: 12, stiffness: 80 },
  });

  const taglineSpring = spring({
    frame: frame - 450,
    fps,
    config: { damping: 14, stiffness: 100 },
  });

  // Slow zoom effect across the whole scene
  const bgZoom = interpolate(frame, [0, durationInFrames], [1, 1.08], {
    extrapolateRight: "clamp",
  });

  // Fade-out at the very end
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 20, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at top, #1e1b4b 0%, #0a0e1a 60%, #000000 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
        overflow: "hidden",
        opacity: fadeOut,
      }}
    >
      {/* Animated gradient orbs */}
      <div
        style={{
          position: "absolute",
          top: "10%",
          left: "15%",
          width: "500px",
          height: "500px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)",
          filter: "blur(60px)",
          transform: `scale(${bgZoom}) translate(${Math.sin(frame / 30) * 20}px, ${Math.cos(frame / 40) * 15}px)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "15%",
          right: "10%",
          width: "450px",
          height: "450px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(236,72,153,0.12) 0%, transparent 70%)",
          filter: "blur(60px)",
          transform: `scale(${bgZoom}) translate(${Math.cos(frame / 35) * 25}px, ${Math.sin(frame / 45) * 20}px)`,
        }}
      />

      {/* DNA helix animated background */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          right: "-100px",
          fontSize: "500px",
          opacity: 0.04,
          transform: `translateY(-50%) rotate(${frame * 0.4}deg)`,
        }}
      >
        🧬
      </div>

      {/* Grid overlay */}
      <svg
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          opacity: 0.04,
        }}
      >
        <defs>
          <pattern
            id="grid"
            width="60"
            height="60"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 60 0 L 0 0 0 60"
              fill="none"
              stroke="#60a5fa"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>

      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          padding: "80px",
        }}
      >
        {/* Main title */}
        <div
          style={{
            transform: `translateY(${(1 - titleSpring) * 60}px) scale(${
              0.85 + titleSpring * 0.15
            })`,
            opacity: titleSpring,
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: "140px",
              fontWeight: 800,
              background: "linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
              letterSpacing: "-4px",
              marginBottom: "16px",
              lineHeight: 1,
            }}
          >
            Anukriti PGx
          </div>
          <div
            style={{
              fontSize: "32px",
              fontWeight: 300,
              color: "#94a3b8",
              letterSpacing: "6px",
              textTransform: "uppercase",
            }}
          >
            Pharmacogenomic Intelligence · Superpower
          </div>
        </div>

        {/* Stat callout */}
        <div
          style={{
            marginTop: "100px",
            opacity: statSpring,
            transform: `translateY(${(1 - statSpring) * 30}px)`,
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: "24px",
              color: "#cbd5e1",
              marginBottom: "16px",
              letterSpacing: "2px",
              textTransform: "uppercase",
            }}
          >
            A clinical reality hiding in plain sight:
          </div>
          <div
            style={{
              fontSize: "80px",
              fontWeight: 800,
              color: "#fbbf24",
              lineHeight: 1.1,
              textShadow: "0 0 40px rgba(251, 191, 36, 0.3)",
            }}
          >
            14% of South Asians
          </div>
          <div
            style={{
              fontSize: "44px",
              color: "#f1f5f9",
              marginTop: "8px",
              fontWeight: 400,
            }}
          >
            cannot activate clopidogrel.
          </div>
        </div>

        {/* Tagline at bottom */}
        <div
          style={{
            position: "absolute",
            bottom: "140px",
            opacity: taglineSpring,
            transform: `translateY(${(1 - taglineSpring) * 20}px)`,
          }}
        >
          <div
            style={{
              padding: "16px 32px",
              background: "rgba(96, 165, 250, 0.1)",
              border: "1px solid rgba(96, 165, 250, 0.3)",
              borderRadius: "100px",
              fontSize: "26px",
              color: "#93c5fd",
              fontWeight: 500,
              textAlign: "center",
              letterSpacing: "0.5px",
            }}
          >
            Current systems ignore ancestry. We fix that.
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
