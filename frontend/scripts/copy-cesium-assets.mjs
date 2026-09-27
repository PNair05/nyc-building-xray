import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const cesiumBuild = join(frontendRoot, "node_modules", "cesium", "Build", "Cesium");
const outputRoot = join(frontendRoot, "public", "cesium");
const assetDirectories = ["Assets", "ThirdParty", "Widgets", "Workers"];

if (!existsSync(cesiumBuild)) {
  throw new Error("Cesium is not installed. Run npm install before copying its browser assets.");
}

mkdirSync(outputRoot, { recursive: true });
for (const directory of assetDirectories) {
  cpSync(join(cesiumBuild, directory), join(outputRoot, directory), {
    recursive: true,
    force: true,
  });
}

console.log(`Copied Cesium browser assets to ${outputRoot}`);
