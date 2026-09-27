import { ImageResponse } from "next/og";

export const alt = "CareerCraft AI — Apply smarter. Tailor faster.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0a0a",
          color: "#fff9df",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            fontSize: 32,
            fontWeight: 600,
            color: "#8fd4a8",
            marginBottom: 32,
          }}
        >
          CareerCraft AI
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 72,
            fontWeight: 700,
            textAlign: "center",
            maxWidth: 900,
            lineHeight: 1.1,
          }}
        >
          Land your next job while you sleep
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 28,
            color: "#DEDBC8",
            marginTop: 32,
            textAlign: "center",
            maxWidth: 800,
          }}
        >
          AI agents that find roles, tailor your resume, and follow up — automatically
        </div>
      </div>
    ),
    { ...size },
  );
}
