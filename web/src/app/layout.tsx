import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AID GRID | Humanitarian Coordination",
  description: "Privacy-preserving humanitarian coordination command board.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
