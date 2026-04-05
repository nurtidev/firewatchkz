import type { Metadata } from "next";
import { CityProvider } from "@/context/CityContext";
import "./globals.css";

export const metadata: Metadata = {
  title: "FireWatch — AI пожарная аналитика",
  description: "Предиктивная аналитика пожарной безопасности на основе AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className="h-full">
      <body className="min-h-full bg-gray-950 text-white antialiased">
        <CityProvider>{children}</CityProvider>
      </body>
    </html>
  );
}
