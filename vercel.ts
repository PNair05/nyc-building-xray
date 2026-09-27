import type { VercelConfig } from "@vercel/config/v1";


export const config: VercelConfig = {
  framework:
    process.env.VERCEL_PROJECT_NAME === "nyc-building-xray-api"
      ? "fastapi"
      : "nextjs",
};
