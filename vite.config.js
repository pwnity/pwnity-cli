import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
    // The root directory for the Vite dev server is now the project root.
    // This simplifies path resolution for assets located in subdirectories like 'plugins/web_ui/static'.
    // Vite will now correctly find `index.html` at `plugins/web_ui/templates/index.html`.
    root: path.resolve(__dirname),



    build: {
        // Das Ausgabeverzeichnis für die gebündelten Dateien.
        // The output directory for bundled files.
        outDir: path.resolve(__dirname, 'plugins/web_ui/static/dist'),
        emptyOutDir: true, // Leert das Verzeichnis vor jedem Build

        // Erzeugt eine `manifest.json`, die für die Backend-Integration nützlich ist.
        manifest: true,

        rollupOptions: {
            // Der Einstiegspunkt deiner JavaScript-Anwendung.
            // We also need to specify the HTML file as an input so Vite knows how to serve it in dev mode.
            input: path.resolve(__dirname, 'plugins/web_ui/templates/index.html'),
            output: {
                // Sorgt für konsistente Dateinamen im `dist`-Ordner.
                entryFileNames: `[name].js`,
                chunkFileNames: `[name].js`,
                assetFileNames: `[name].[ext]`
            }
        }
    },

    css: {
        preprocessorOptions: {
            css: {
                // Exclude the loader CSS from the bundle, as it's loaded directly in HTML.
                // This prevents duplicate styles in production.
                url: (url) => !url.includes('_loader.css')
            }
        }
    },

    server: {
        // Leitet API-Anfragen während der Entwicklung an dein Flask-Backend weiter.
        proxy: {
            '/api': 'http://127.0.0.1:5001',
            '/view': 'http://127.0.0.1:5001',
            '/socket.io': { target: 'http://127.0.0.1:5001', ws: true },
        }
    }
});