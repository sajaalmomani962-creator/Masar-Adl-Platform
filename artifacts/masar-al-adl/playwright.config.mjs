import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const output = fileURLToPath(new URL("../../generated-artifacts/browser/", import.meta.url));
const systemChromium = "/repl/tools/bin/chromium";

export default defineConfig({
  testDir: "./masar_adl/tests/browser",
  testMatch: "**/*.spec.mjs",
  outputDir: `${output}/results`,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 8_000 },
  reporter: [
    ["list"],
    ["html", { outputFolder: `${output}/report`, open: "never" }],
    ["json", { outputFile: `${output}/results.json` }],
  ],
  use: {
    // Deliberately not configurable to a remote/live target.
    baseURL: "http://127.0.0.1:8765",
    actionTimeout: 8_000,
    navigationTimeout: 15_000,
    locale: "ar-JO",
    launchOptions: existsSync(systemChromium) ? { executablePath: systemChromium } : {},
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } } },
    { name: "phone", use: { browserName: "chromium", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: "python masar_adl/tests/browser/server.py",
    url: "http://127.0.0.1:8765/health",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
