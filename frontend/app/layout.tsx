import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cortex",
  description: "A second brain for students.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
