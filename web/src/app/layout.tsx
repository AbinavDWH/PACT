import type { Metadata, Viewport } from "next";
import "./fonts.css";
import "./globals.css";

// Fira Sans / Fira Code are self-hosted from public/fonts rather than linked
// from fonts.googleapis.com or fetched by next/font at build time. The standing
// assumption in this project is that the venue network fails, so the font files
// are committed and served locally; the CSS variables still fall through to
// system-ui / ui-monospace if a face ever fails to load.

export const metadata: Metadata = {
  // Was "AID GRID | Humanitarian Coordination" while every surface in the app
  // is branded PACT -- the browser tab named a different product.
  title: "PACT | Humanitarian Coordination",
  description:
    "Privacy-preserving humanitarian coordination console: live agent " +
    "deliberation, geographic matching and allocation review.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // No maximumScale/userScalable: pinch-zoom stays available. Disabling it is
  // the most common accessibility regression on a data-dense dark UI.
  themeColor: "#0b0f14",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
