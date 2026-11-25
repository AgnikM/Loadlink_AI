import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LoadLink AI • B2B Freight Marketplace MVP",
  description: "Deterministic 7-factor matching, live route tracking, and automated backhaul return load discovery across the Kolkata-Durgapur-Asansol corridor.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased font-sans"
    >
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
