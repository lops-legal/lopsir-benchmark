# C1 - localização de referências e identidades

**Primeira rodada real concluída:** cinco métodos, PostgreSQL 18, 358.448 registros físicos e 341.827 identidades distintas. Fonte exclusiva: [leis-mcp](https://github.com/lops-legal/leis-mcp), lida sem modificações.

- [Resultados, gráficos e limites](../../reports/c1/real/README.md).
- [Arquitetura executada, dependências e reprodução](EXECUCAO.md).
- [Cinco métodos, artigos e hipóteses](METODOLOGIAS.md).
- [Registro de métodos](../../configs/c1.methods.json) e [pipeline comum](../PIPELINE.md).

C1 localiza a identidade explicitamente referenciada. C2 pesquisa expressão/trecho; C3 busca fundamentos para um problema descrito. Os cinco métodos desta branch são igualdade B-tree, BM25S, pg_trgm GiST, Levenshtein RapidFuzz e Fellegi-Sunter/Splink. Nenhum usa embedding, GPU ou API.

As mesmas 305 consultas de teste foram executadas três vezes por método: sete chamadas existentes na fonte e 298 referências derivadas de metadados reais. Não são logs reais de uso e não incluem erros artificiais nem histórias jurídicas inventadas. A auditoria de 507 consultas, incluindo treino/dev, não encontrou vazamento de identidade ou positivos sem correspondência no banco.

A busca exata e o Splink atingiram 100% Hit@1 neste lote íntegro, com p95 de 1,27 ms e 228,73 ms, respectivamente. A construção dos positivos por identidade favorece naturalmente igualdade. Não extrapolar para busca semântica, inexistentes, referências divergentes ou produção concorrente.

O preflight continua sendo uma verificação de configuração local, sem métricas de pesquisa. Defina LEIS_MCP_ROOT para o clone real; sem arquivos locais ele registra os pré-requisitos ausentes. O resultado científico medido está em reports/c1/real, não no relatório de prontidão.
