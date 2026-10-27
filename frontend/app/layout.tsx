import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CloudOps AI — Incident Intelligence",
  description: "Evidence-first incident investigation for modern software systems.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
