/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  turbopack: {
    root: __dirname,
  },
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: process.env.WATCHPACK_POLLING === 'true' ? 1000 : false,
        aggregateTimeout: 300,
        ignored: ['**/node_modules/**', '**/.git/**'],
      };
    }
    return config;
  },
  async rewrites() {
    const apiUrl = process.env.API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
