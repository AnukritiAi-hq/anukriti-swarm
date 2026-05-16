import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
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

const EASE_OUT_EXPO = Easing.bezier(0.16, 1, 0.3, 1);

export const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Title fades + rises
  const titleOpacity = interpolate(frame, [5, 30], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });
  const titleY = interpolate(frame, [5, 30], [40, 0], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });

  // Subtitle
  const subtitleOpacity = interpolate(frame, [30, 55], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });

  // The stat — bigger reveal
  const statOpacity = interpolate(frame, [80, 110], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });
  const statScale = interpolate(frame, [80, 110], [0.9, 1], {
    extrapolateRight: "clamp",
    easing: EASE_OUT_EXPO,
  });

  // Tagline near end
  const taglineOpacity = interpolate(
    frame,
    [Math.max(0, durationInFrames - 120), Math.max(0, durationInFrames - 90)],
    [0, 1],
    { extrapolateRight: "clamp", extrapolateLeft: "clamp", easing: EASE_OUT_EXPO },
  );

  // Background slow zoom
  const bgZoom = interpolate(frame, [0, durationInFrames], [1, 1.05], {
    extrapolateRight: "clamp",
  });

  // Floating orbs
  const orb1X = Math.sin(frame / 45) * 30;
  const orb1Y = Math.cos(frame / 55) * 20;
  const orb2X = Math.cos(frame / 40) * 25;
  const orb2Y = Math.sin(frame / 60) * 30;

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at 50% 30%, #1e1b4b 0%, #0a0e1a 60%, #000000 100%)",
        fontFamily: inter,
        overflow: "hidden",
      }}
    >
      {/* Gradient orbs */}
      <div
        style={{
          position: "absolute",
          top: "15%",
          left: "15%",
          width: "520px",
          height: "520px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(99,102,241,0.18) 0%, transparent 70%)",
          filter: "blur(60px)",
          transform: `scale(${bgZoom}) translate(${orb1X}px, ${orb1Y}px)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: "10%",
          right: "10%",
          width: "480px",
          height: "480px",
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(236,72,153,0.12) 0%, transparent 70%)",
          filter: "blur(60px)",
          transform: `scale(${bgZoom}) translate(${orb2X}px, ${orb2Y}px)`,
        }}
      />

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
          <pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse">
            <path d="M 80 0 L 0 0 0 80" fill="none" stroke="#60a5fa" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>

      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          padding: "120px 80px",
        }}
      >
        <div
          style={{
            transform: `translateY(${titleY}px)`,
            opacity: titleOpacity,
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
              letterSpacing: "-4px",
              lineHeight: 1,
              marginBottom: "18px",
            }}
          >
            Anukriti PGx
          </div>
          <div
            style={{
              fontSize: "28px",
              fontWeight: 400,
              color: "#94a3b8",
              letterSpacing: "6px",
              textTransform: "uppercase",
              opacity: subtitleOpacity,
            }}
          >
            Pharmacogenomic Intelligence · Superpower
          </div>
        </div>

        <div
          style={{
            marginTop: "100px",
            opacity: statOpacity,
            transform: `scale(${statScale})`,
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: "22px",
              color: "#cbd5e1",
              fontWeight: 500,
              marginBottom: "18px",
              letterSpacing: "2px",
              textTransform: "uppercase",
            }}
          >
            A clinical reality hiding in plain sight
          </div>
          <div
            style={{
              fontSize: "88px",
              fontWeight: 800,
              color: "#fbbf24",
              lineHeight: 1.05,
              textShadow: "0 0 50px rgba(251,191,36,0.35)",
            }}
          >
            14% of South Asians
          </div>
          <div
            style={{
              fontSize: "44px",
              color: "#f1f5f9",
              marginTop: "12px",
              fontWeight: 400,
            }}
          >
            cannot activate clopidogrel.
          </div>
        </div>

        <div
          style={{
            position: "absolute",
            bottom: "180px",
            opacity: taglineOpacity,
          }}
        >
          <div
            style={{
              padding: "18px 34px",
              background: "rgba(96,165,250,0.1)",
              border: "1px solid rgba(96,165,250,0.35)",
              borderRadius: "100px",
              fontSize: "26px",
              color: "#93c5fd",
              fontWeight: 500,
            }}
          >
            Current systems ignore ancestry. We fix that.
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
