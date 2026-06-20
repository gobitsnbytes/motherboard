/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@bnb/ui"],
  async rewrites() {
    return {
      fallback: [
        {
          source: '/api/:path*',
          destination: `${process.env.API_URL || 'http://api:8000'}/api/:path*`,
        },
      ],
    };
  },
};

module.exports = nextConfig;
