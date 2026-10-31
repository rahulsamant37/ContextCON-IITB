import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/shell";

export const metadata: Metadata = {
  title: { default: "MarketEntry", template: "%s · MarketEntry" },
  description: "Research a new market in minutes: target companies, decision-makers, competitors and market size, every number linked to its source.",
};

const themeScript = `try{var t=localStorage.getItem('theme');if(t==='dark')document.documentElement.classList.add('dark')}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body><Providers><Shell>{children}</Shell></Providers></body>
    </html>
  );
}
