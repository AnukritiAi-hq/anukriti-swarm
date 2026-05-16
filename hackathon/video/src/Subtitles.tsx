import type { Caption, TikTokPage } from "@remotion/captions";
import { createTikTokStyleCaptions } from "@remotion/captions";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AbsoluteFill,
  Sequence,
  cancelRender,
  delayRender,
  continueRender,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const { fontFamily: interFamily } = loadInter("normal", {
  weights: ["500", "700", "800"],
  subsets: ["latin"],
});

const HIGHLIGHT_COLOR = "#fbbf24";
const TEXT_COLOR = "#ffffff";
const SWITCH_EVERY_MS = 1200;

export const Captions: React.FC = () => {
  const { fps } = useVideoConfig();
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const [handle] = useState(() => delayRender("fetching captions"));

  const fetchCaptions = useCallback(async () => {
    try {
      const res = await fetch(staticFile("captions.json"));
      const data = (await res.json()) as Caption[];
      setCaptions(data);
      continueRender(handle);
    } catch (e) {
      cancelRender(e);
    }
  }, [handle]);

  useEffect(() => {
    fetchCaptions();
  }, [fetchCaptions]);

  const pages = useMemo(() => {
    if (!captions) return null;
    return createTikTokStyleCaptions({
      captions,
      combineTokensWithinMilliseconds: SWITCH_EVERY_MS,
    }).pages;
  }, [captions]);

  if (!pages) return null;

  return (
    <AbsoluteFill>
      {pages.map((page, index) => {
        const nextPage = pages[index + 1] ?? null;
        const startFrame = (page.startMs / 1000) * fps;
        const endFrame = Math.min(
          nextPage ? (nextPage.startMs / 1000) * fps : Infinity,
          startFrame + (SWITCH_EVERY_MS / 1000) * fps,
        );
        const durationInFrames = endFrame - startFrame;
        if (durationInFrames <= 0) return null;

        return (
          <Sequence key={index} from={startFrame} durationInFrames={durationInFrames}>
            <CaptionPage page={page} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const CaptionPage: React.FC<{ page: TikTokPage }> = ({ page }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentTimeMs = (frame / fps) * 1000;
  const absoluteTimeMs = page.startMs + currentTimeMs;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: "60px",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          padding: "18px 36px",
          background: "rgba(0, 0, 0, 0.78)",
          backdropFilter: "blur(10px)",
          borderRadius: "16px",
          border: "1px solid rgba(255,255,255,0.08)",
          maxWidth: "1400px",
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontFamily: interFamily,
            fontWeight: 700,
            fontSize: "38px",
            lineHeight: 1.25,
            letterSpacing: "-0.2px",
            whiteSpace: "pre",
            textShadow: "0 2px 10px rgba(0,0,0,0.5)",
          }}
        >
          {page.tokens.map((token) => {
            const isActive =
              token.fromMs <= absoluteTimeMs && token.toMs > absoluteTimeMs;
            return (
              <span
                key={`${token.fromMs}-${token.toMs}`}
                style={{
                  color: isActive ? HIGHLIGHT_COLOR : TEXT_COLOR,
                  transition: "none",
                }}
              >
                {token.text}
              </span>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
