/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxied server-side, damit der Browser das Backend nie direkt (anderer
  // Port/Host) ansprechen muss - vermeidet CORS und funktioniert auch dort,
  // wo der Client keinen direkten Netzwerkzugriff auf das Backend hat.
  async rewrites() {
    const backendUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

module.exports = nextConfig;
