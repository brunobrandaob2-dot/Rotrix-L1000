# Aviso de origem

O app **Rotrix L-1000** (pasta `app/`) é uma cópia modificada do **Handy**
(https://github.com/cjpais/Handy), de CJ Pais, distribuído sob a licença MIT
(ver `LICENSE`, mantido sem alterações). Commit de origem: `UPSTREAM_HANDY_COMMIT.txt`.

O nome, o logotipo, o ícone e a identidade visual "Handy" não são de código aberto
e não são usados aqui: o Rotrix L-1000 tem nome, ícone e logotipo próprios e não
sugere endosso do projeto original.

Principais mudanças em relação ao Handy:
- nome, identificador (`com.rotrix.l1000`), ícones, logotipo e textos da interface;
- o Roteador de Laudos vem embutido e é iniciado junto com o app (`src-tauri/src/rotrix.rs`);
- padrões para radiologia em pt-BR: pós-processamento pelo roteador local,
  Ctrl+Espaço = ditado com roteador, Ctrl+Shift+Espaço = ditado livre,
  vocabulário de radiologia, colagem com negrito;
- sem busca de atualizações do Handy original e sem assinatura de código do autor original.
