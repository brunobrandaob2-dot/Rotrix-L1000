# app/ — Rotrix L-1000

App único de ditado radiológico: cópia própria do Handy (Tauri v2 + Rust + React/TypeScript, MIT; ver `NOTICE.md`) com o Roteador de Laudos embutido.

- **Compilação:** o GitHub Actions (`.github/workflows/build-windows.yml`) gera o instalador de Windows a cada envio. O instalador fica em Actions → execução → Artifacts.
- **Roteador embutido:** no CI, o Python embutido oficial, o `roteador-atual/` (máscaras + banco) e o colador com negrito são colocados em `src-tauri/resources/rotrix/`. Ao abrir, o app copia o roteador para `%APPDATA%\com.rotrix.l1000\roteador` e o inicia na porta 8123 (`src-tauri/src/rotrix.rs`).
- **Especificação completa:** `../docs/PROMPT_MESTRE_Roteador_de_Laudos.md`.
