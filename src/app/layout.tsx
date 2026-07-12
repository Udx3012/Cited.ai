import type { Metadata } from "next";
import { Instrument_Serif, Raleway } from "next/font/google";
import "./globals.css";

const instrumentSerif = Instrument_Serif({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["400"],
  style: ["normal", "italic"],
  display: "swap",
});

const raleway = Raleway({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cited.ai | Let your documents answer for you",
  description: "A grounded retrieval platform for teams that can't afford hallucinations. Upload once, ask anything with page-level citations and a verifiable trail.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${instrumentSerif.variable} ${raleway.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col bg-[#030303] text-zinc-100 font-sans selection:bg-[#c5a880]/30 selection:text-white">
        {children}
      </body>
    </html>
  );
}
