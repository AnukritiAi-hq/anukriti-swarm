import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  spring,
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
  sceneNumber: string;
};

export const ClipScene: React.FC<Props> = ({
  title,
  subtitle,
  clipSrc,
  highlightText,
  accent,
  sceneNumber,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();

  const headerSpring = spring({
    frame: frame - 5,
    fps,
    config: { damping: 18, stiffness: 120 },
  });

  const clipScale = spring({
    frame: frame - 15,
    fps,
    config: { damping: 20, stiffness: 100 },
  });

  const clipOpacity = interpolate(frame, [15, 45], [0, 1], {
    extrapolateRight: "clamp",
  });

  const highlightSpring = spring({
    frame: frame - (durationInFrames - 120),
    fps,
    config: { damping: 15, stiffness: 100 },
  });

  // Fade out at the end
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 15, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0a0e1a 0%, #111827 100%)",
        fontFamily: "system-ui, -apple-system, sans-serif",
        opacity: fadeOut,
      }}
    >
      {/* Accent gradient glow */}
      <div
        style={{
          position: "absolute",
          top: "-200px",
          left: "50%",
          transform: "translateX(-50%)",
          width: "1000px",
          height: "600px",
          borderRadius: "50%",
          background: `radial-gradient(ellipse, ${accent}22 0%, transparent 60%)`,
          filter: "blur(40px)",
        }}
      />

      {/* Top header */}
      <div
        style={{
          opacity: headerSpring,
          transform: `translateY(${(1 - headerSpring) * -20}px)`,
          padding: "40px 80px 20px 80px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
          {/* Scene number badge */}
          <div
            style={{
              width: "80px",
              height: "80px",
              borderRadius: "20px",
              background: `${accent}20`,
              border: `2px solid ${accent}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "38px",
              fontWeight: 800,
              color: accent,
            }}
          >
            {sceneNumber}
          </div>
          <div>
            <div
              style={{
                fontSize: "18px",
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
                fontSize: "52px",
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
                fontSize: "22px",
                color: "#94a3b8",
                marginTop: "6px",
              }}
            >
              {subtitle}
            </div>
          </div>
        </div>
        {/* Corner branding */}
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
              fontSize: "28px",
              fontWeight: 800,
              color: "#ffffff",
              letterSpacing: "2px",
            }}
          >
            ANUKRITI PGx
          </div>
          <div
            style={{
              fontSize: "14px",
              color: "#64748b",
              letterSpacing: "3px",
            }}
          >
            MCP · SHARP · FHIR
          </div>
        </div>
      </div>

      {/* Video clip in a polished frame */}
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 80px 140px 80px",
          opacity: clipOpacity,
          transform: `scale(${0.92 + clipScale * 0.08})`,
        }}
      >
        <div
          style={{
            position: "relative",
            width: "100%",
            height: "100%",
            borderRadius: "20px",
            overflow: "hidden",
            border: `2px solid ${accent}55`,
            boxShadow: `0 40px 100px ${accent}33, 0 0 0 1px rgba(255,255,255,0.05) inset`,
            background: "#000",
          }}
        >
          {/* Browser-style chrome bar */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: "36px",
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
              <div
                style={{
                  width: "12px",
                  height: "12px",
                  borderRadius: "50%",
                  background: "#ef4444",
                }}
              />
              <div
                style={{
                  width: "12px",
                  height: "12px",
                  borderRadius: "50%",
                  background: "#fbbf24",
                }}
              />
              <div
                style={{
                  width: "12px",
                  height: "12px",
                  borderRadius: "50%",
                  background: "#22c55e",
                }}
              />
            </div>
            <div
              style={{
                flex: 1,
                textAlign: "center",
                fontSize: "13px",
                color: "#94a3b8",
                fontFamily: "monospace",
              }}
            >
              app.promptopinion.ai
            </div>
            <div style={{ width: "60px" }} />
          </div>

          <OffthreadVideo
            src={staticFile(clipSrc)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              paddingTop: "36px",
              boxSizing: "border-box",
            }}
            muted
            startFrom={0}
          />
        </div>
      </div>

      {/* Bottom highlight banner */}
      <div
        style={{
          position: "absolute",
          bottom: "40px",
          left: 0,
          right: 0,
          opacity: highlightSpring,
          transform: `translateY(${(1 - highlightSpring) * 20}px)`,
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
            padding: "18px 44px",
            fontSize: "26px",
            color: "#ffffff",
            fontWeight: 600,
            letterSpacing: "0.5px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
            boxShadow: `0 10px 40px ${accent}33`,
          }}
        >
          <span style={{ fontSize: "28px" }}>✓</span>
          {highlightText}
        </div>
      </div>
    </AbsoluteFill>
  );
};
