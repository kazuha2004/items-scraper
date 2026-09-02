import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      // Amazon product images
      { protocol: "https", hostname: "images-na.ssl-images-amazon.com" },
      { protocol: "https", hostname: "m.media-amazon.com" },
      // Flipkart product images
      { protocol: "https", hostname: "rukminim2.flixcart.com" },
      { protocol: "https", hostname: "rukminim1.flixcart.com" },
      // Meesho product images
      { protocol: "https", hostname: "images.meesho.com" },
      { protocol: "https", hostname: "cdn.meesho.com" },
    ],
  },
};

export default nextConfig;
