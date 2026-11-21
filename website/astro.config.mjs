import { defineConfig } from 'astro/config';

export default defineConfig({
  integrations: [{
    name: 'mobile-dev-qr',
    hooks: {
      'astro:server:setup'({ server }) {
        server.httpServer?.once('listening', () => setImmediate(async () => {
          const { renderUnicodeCompact } = await import('uqr');
          for (const url of server.resolvedUrls?.network ?? []) {
            console.log(`Scan on the same Wi-Fi: ${url}\n${renderUnicodeCompact(url)}`);
          }
        }));
      },
    },
  }],
});
