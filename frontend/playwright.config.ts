import { defineConfig } from '@playwright/test';

// A dedicated port prevents tests from accidentally reusing another project's server.
export default defineConfig({
  testDir: './tests',
  outputDir: 'test-results',
  use: {
    channel: 'chromium',
    baseURL: 'http://127.0.0.1:5175',
    launchOptions: { args: ['--enable-unsafe-swiftshader'] },
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5175',
    url: 'http://127.0.0.1:5175',
    reuseExistingServer: false,
  },
});
