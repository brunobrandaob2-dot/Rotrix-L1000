# Rotrix L-1000

**Roteador de Laudos**: ditado radiológico local com máscaras, formatação no padrão do laudo e IA opcional com a chave de cada usuário. "Rotrix L-1000" é o nome do protótipo; a marca final está em aberto.

> Repositório privado. Não coloque aqui chaves de API, histórico de ditados, arquivos do Radius, DICOM nem qualquer laudo com dado de paciente (ver `.gitignore`).

## O que tem aqui

| Pasta | Conteúdo |
|---|---|
| `docs/PROMPT_MESTRE_Roteador_de_Laudos.md` | **Especificação completa do app.** Comece por aqui. |
| `docs/prototipo/` | Protótipo em PDF (2 páginas) e o HTML-fonte para gerar de novo |
| `docs/ESPECIFICACAO_MASCARAS.md` | Como escrever máscaras, blocos, frases e gatilhos |
| `docs/COLA_ROTEADOR.html` | Cola de uso do dia a dia |
| `roteador-atual/` | O sistema que funciona hoje (versão do motor 2026-09-21.6): roteador, formatador, IA (nuvem.py), atalho Ctrl+Alt+A, 47 regiões de máscaras, dicionário de ouvido, instalador e atualizador para Windows |
| `app/` | O app único (fork do Handy), em construção |

## Sistema atual (Windows)

- **Instalação:** `roteador-atual/INSTALAR.ps1`.
- **Atualização:** `APLICAR_ATUALIZACAO.ps1`.
- **Banco:** `construir_base.py` gera o `base.sqlite` a partir de `dados/mascaras/`.
- **Validação de uma região:** `python validar_regiao.py dados/mascaras/<categoria>/<modalidade>/<regiao>` (zero erro obrigatório).

O GitHub Actions (`.github/workflows/validar-mascaras.yml`) gera o banco e valida todas as regiões a cada mudança.

## Roteiro

1. Cópia própria do Handy (nome e ícone novos, aviso MIT).
2. Roteador e formatador dentro do app; modo flutuante; escuta contínua; "formar laudo".
3. Fila do Radius, modo estação, modo escuro.
4. IA com chave própria (provedor → modelo, tabela por exame, "só formatar" × "analisar", contador de tokens).
5. Perfis e aba de Máscaras do usuário.
