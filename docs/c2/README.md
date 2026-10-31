# C2 — expressões jurídicas e palavras-chave

Estado: preparação documental; execução aguarda conclusão e revisão de C1. Branch destinada ao trabalho do Claude: `c2`. Seguir [o pipeline comum](../PIPELINE.md).

## Intenção e dados

Encontrar documentos pertinentes a uma expressão, combinação de termos jurídicos ou trecho literal no acervo real do projeto. Não localizar uma identidade conhecida (C1) nem transformar toda consulta curta em uma pergunta fática C3. Frases exatas e termos conceituais serão etiquetas separadas.

Usar exclusivamente os dados indicados pelo usuário no LopsIR. Não importar novos benchmarks. As coleções JUÁ já descritas no SDD são referências metodológicas; presença de links não significa que seus arquivos estejam no projeto.

## Cinco vagas metodológicas propostas para a seleção de C2

Estas são famílias candidatas para detalhar depois de C1, não cinco implementações prontas:

| Vaga | Família | Artigo | Código público |
|---|---|---|---|
| 1 | BM25 ajustado | [Pyserini](https://arxiv.org/abs/2102.10073) | [castorini/pyserini](https://github.com/castorini/pyserini) |
| 2 | BM25 com expansão documental | [doc2query](https://arxiv.org/abs/1904.08375) | [castorini/docTTTTTquery](https://github.com/castorini/docTTTTTquery) |
| 3 | Esparso aprendido | [SPLADE-v3](https://arxiv.org/abs/2403.06789) | [naver/splade](https://github.com/naver/splade) |
| 4 | Denso de um vetor | [Qwen3 Embedding](https://arxiv.org/abs/2506.05176) | [QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding) |
| 5 | Fusão lexical+densa | [An Analysis of Fusion Functions](https://arxiv.org/abs/2210.11934) | [AmenRa/ranx](https://github.com/AmenRa/ranx) para fusão/avaliação; recuperadores anteriores |

Português e domínio jurídico precisam ser validados para cada checkpoint; não chamar um checkpoint inglês de adequado sem experimento. A biblioteca de fusão não é alegada como implementação oficial do artigo. RRF e combinação convexa são variantes publicadas; seus parâmetros são ajustados só no dev.

Cada vaga exige ficha completa de versões, dependências, corpus, prompts/instruções quando aplicáveis, parâmetros e custo. Uma variante com reranqueamento deve ser uma ablação explicitamente identificada; não pode substituir silenciosamente a metodologia da linha principal nem multiplicar o total de métodos sem controle.

## Critérios

Principais: nDCG@10 e Precision@10/20; complementares: MRR@10, Recall@20/100, cobertura dos julgamentos e erros por expressão literal, negação e terminologia. Acrescentar todos os critérios de rapidez, recursos, ingestão, atualização e custo do pipeline comum.

## Entrega exigida ao abrir esta etapa

Cinco fichas fundamentadas e executáveis, dados reais e qrels auditados, cinco relatórios comparáveis e conclusão por vantagem/custo. Não começar C3 antes da revisão. Consultas G1/G2 do JurisTCU podem motivar a classificação, mas não serão baixadas ou adicionadas sem instrução do usuário.
