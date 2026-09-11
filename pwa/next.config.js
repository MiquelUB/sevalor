/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  distDir: 'dist',
  images: { unoptimized: true },
  reactStrictMode: true,
  trailingSlash: true,
};

module.exports = nextConfig;