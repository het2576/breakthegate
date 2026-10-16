import type { Metadata, Viewport } from "next";
import { Archivo, Atkinson_Hyperlegible_Next, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// PRD 11.2: Archivo for signage (width axis), Atkinson Hyperlegible Next for
// body and labels, JetBrains Mono only for commands.
const archivo = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  variable: "--font-archivo",
  display: "swap",
});
const atkinson = Atkinson_Hyperlegible_Next({
  subsets: ["latin"],
  variable: "--font-atkinson",
  // "swap" caused a visible reflow: next/font has no metrics to size-match this font's
  // fallback, so when it swapped in after first paint, text reflowed and shifted layout
  // (the P5/P6 "no layout shift" requirement). "optional" never swaps after first paint.
  display: "optional",
});
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Break the gate",
  description: "An AI gate decides if a command is safe to run. Trick it into saying yes.",
};

export const viewport: Viewport = {
  themeColor: "#1f3fd6",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${atkinson.variable} ${jetbrains.variable}`}
    >
      <body className="flex min-h-dvh flex-col bg-paper text-ink antialiased">{children}</body>
    </html>
  );
}
