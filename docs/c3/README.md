# C3 — problema ou questão em linguagem natural

Estado: preparação documental; execução aguarda conclusão e revisão de C2. Branch: `c3`. Seguir [o pipeline comum](../PIPELINE.md).

## Definição

Uma pergunta, tese descrita ou situação fática procura textos que forneçam fundamentos pertinentes. C3 envolve match problema–fundamento; semelhança textual sozinha não demonstra aplicação jurídica. Não se restringe a um relato de fatos: enunciado abstrato procurando excerto também pode se enquadrar em C3.

JUÁ-Juris e BR-TaxQA são referências dessa formulação; JurisTCU, NormasTCU e Ulysses contêm outras formulações a revisar. Isso não converte as coleções automaticamente em consultas do acervo de 370 mil documentos. Trabalhar somente sobre os arquivos/conexões fornecidos pelo usuário.

## Cinco vagas metodológicas propostas

| Vaga | Família | Artigo | Código público |
|---|---|---|---|
| 1 | Recuperação densa | [Qwen3](https://arxiv.org/abs/2506.05176) | [QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding) |
| 2 | Recuperação esparsa aprendida | [SPLADE-v3](https://arxiv.org/abs/2403.06789) | [naver/splade](https://github.com/naver/splade) |
| 3 | Recuperação multivetorial | [BGE-M3](https://arxiv.org/abs/2402.03216) | [FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) |
| 4 | Híbrido lexical+denso | [Fusão lexical-semântica](https://arxiv.org/abs/2210.11934) | [Pyserini](https://github.com/castorini/pyserini) + [ranx](https://github.com/AmenRa/ranx) |
| 5 | Híbrido com reranqueamento | [Qwen3, incluindo reranking](https://arxiv.org/abs/2506.05176) | [QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding), além dos recuperadores |

São candidatos para a seleção posterior, não uma alegação de que as cinco combinações acima foram publicadas/testadas como pipeline completo no português jurídico. Cada componente deve ser reproduzido conforme sua fonte; a composição é uma adaptação experimental declarada. Versões, checkpoints, português, memória e disponibilidade de API ainda precisam ser fechados. SPLADE não entra em produção portuguesa apenas por ser uma família competitiva em inglês.

## Critérios e ablações previstas

- Relevância: nDCG@10/20, Precision@10/20, Recall@20/100/1000 e MRR@10.
- Pertinência: fatos determinantes, fundamento adotado, negação e distinção entre citação/alegação/voto divergente/decisão.
- Qualidade antes e depois do reranking para separar falha de cobertura de falha de ordenação.
- Todos os critérios de tempo, recursos, custo e atualização do pipeline comum.
- Ablações posteriores: modelo pequeno/maior, ementa/inteiro teor segmentado, quantidade de candidatos, reranking ligado/desligado e compressão.

## Dependências e segredos

Não solicitar chaves agora. A etapa deverá especificar endpoint, modelo, provedor, dimensão, instrução, tokens e teto de gasto antes de usar API. Tokens ficam fora do Git. A GPU local é uma restrição de execução, não uma razão para inventar desempenho de modelos maiores.
