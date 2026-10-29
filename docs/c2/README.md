# C2 — expressões jurídicas e palavras-chave

Estado (29/10/2026): **executado** na branch `c2` pelo Claude, sobre dados reais do JurisTCU, com as cinco metodologias, as ablações e o módulo de resultados. Seguir [o pipeline comum](../PIPELINE.md). Fichas: [METODOLOGIAS.md](METODOLOGIAS.md). Resultados: [reports/c2/RESULTS.md](../../reports/c2/RESULTS.md).

## Intenção

Encontrar documentos pertinentes a uma expressão, combinação de termos jurídicos ou trecho literal. Não localizar uma identidade conhecida (C1) nem transformar toda consulta curta em uma pergunta fática C3.

## Dados — decisão do usuário

Instrução do usuário em 29/10/2026: a base do C2 é o repositório `lops-legal/lopsir-benchmark` e, depois dele, o **JurisTCU, se for facilmente baixável**. Essa instrução substitui, para o C2, a restrição anterior "não importar outro conjunto" do [handoff](HANDOFF-CLAUDE.md).

- O repositório não contém corpus jurídico (o acervo de ~370 mil jurisprudências não tem local; ver `reports/c1/repository-inventory.json`). Ele fornece os contratos, o avaliador e o código.
- O JurisTCU é público no Hugging Face, sem gate: revisão fixada, só `EXCERTO`, 16.045 documentos, 150 consultas, 2.250 qrels graus 0–3. Arquivos baixados ficam em `data/` (ignorado pelo Git); o [manifesto](../../reports/c2/dataset-juristcu.json) guarda hashes e contagens.
- **C2 = consultas 1–100** (50 palavras-chave reais de usuários + 50 sintéticas). As 50 perguntas (101–150) são C3 e não entram em nenhum run C2.
- Quando o acervo de 370 mil tiver local e esquema, ele entra no mesmo formato canônico (`corpus.jsonl`, `queries.jsonl`, `qrels.tsv`) e os cinco módulos rodam sem mudança de código.

## As cinco metodologias

| # | Vantagem testada | Metodologia | Artigo | Código | Execução |
|---|---|---|---|---|---|
| M1 | mais barata | BM25 ajustado (analisador PT, k1/b no dev) | [doi:10.1561/1500000019](https://doi.org/10.1561/1500000019), [bm25s](https://arxiv.org/abs/2407.03618) | [xhluca/bm25s](https://github.com/xhluca/bm25s) | CPU |
| M2 | expansão por LLM | Query2doc sobre o BM25 do M1 (ablação: RM3) | [2303.07678](https://arxiv.org/abs/2303.07678) | sem repo oficial; RM3: [anserini](https://github.com/castorini/anserini) | OpenRouter, Nemotron 3.5 Lightning grátis |
| M3 | esparso aprendido | SPLADE-PT-BR (BERTimbau) em passagens, MaxP/FirstP | [2109.10086](https://arxiv.org/abs/2109.10086), [2403.06789](https://arxiv.org/abs/2403.06789) | [naver/splade](https://github.com/naver/splade), [SPLADE-PT-BR](https://github.com/AxelPCG/SPLADE-PT-BR) | GPU local |
| M4 | modelo único multilíngue | BGE-M3 denso + pesos lexicais | [2402.03216](https://arxiv.org/abs/2402.03216) | [FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) | GPU local |
| M5 | junta tudo | Híbrido BM25 + Nemotron Embed 8B, fusão RRF/convexa no dev (referência: denso puro) | [2210.11934](https://arxiv.org/abs/2210.11934) | [AmenRa/ranx](https://github.com/AmenRa/ranx) | NVIDIA API grátis |

Diferenças em relação às vagas propostas anteriormente: doc2query (vaga 2) foi trocado por Query2doc porque gerar consultas para 16 mil documentos longos excede a cota das APIs gratuitas, enquanto o Query2doc precisa de uma chamada por consulta; o denso Qwen3 (vaga 4) foi trocado por BGE-M3 local, gratuito e com saída lexical própria; o Qwen3 Embedding é pago na OpenRouter e o melhor denso gratuito (Nemotron 3.5 Embed 8B) ficou como ramo do híbrido.

## Como reproduzir

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-c2.txt -e .
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu126
.venv\Scripts\python -m pip install "transformers<5" FlagEmbedding
copy .env.example .env   # preencher OPENROUTER_API_KEY e NVIDIA_API_KEY
.venv\Scripts\python -m lopsir_c2.data                 # baixa e congela o JurisTCU + split
.venv\Scripts\python -m lopsir_c2.m1_bm25              # M1 (congela o BM25 usado por M2/M5)
.venv\Scripts\python -m lopsir_c2.m2_expansion         # M2 + ablação RM3
.venv\Scripts\python -m lopsir_c2.m3_splade            # M3
.venv\Scripts\python -m lopsir_c2.m4_bgem3             # M4
.venv\Scripts\python -m lopsir_c2.m5_hybrid.encode     # vetores Nemotron (retomável)
.venv\Scripts\python -m lopsir_c2.m5_hybrid            # M5 + referência densa
.venv\Scripts\python -m lopsir_c2.results              # summary.json, gráficos, RESULTS.md
.venv\Scripts\python -m unittest tests.test_c2 tests.test_metrics
```

Cada método grava `reports/c2/<método>/result.json` (configuração, grade do dev, métricas por consulta, latência por etapa, recursos e uso de API) e os runs de dev e teste em TSV.

## Resultado (teste, 70 consultas C2)

| Metodologia | Vantagem testada | nDCG@10 | Δ vs BM25 [IC95] | Veredito | p50 por consulta |
|---|---|---|---|---|---|
| **M5 Híbrido** BM25 + Nemotron 8B | junta tudo | **0,364** | +0,023 [+0,010; +0,036] | **superior** | ~2,7 s (embedding da consulta na API) |
| M1 BM25 ajustado | mais barata | 0,341 | baseline | — | 0,25 ms |
| M2 Query2doc | expansão por LLM | 0,306 | −0,035 [−0,060; −0,011] | inferior | ~2,2 s (LLM) |
| M4 BGE-M3 | modelo único multilíngue | 0,283 | −0,058 [−0,112; −0,004] | inferior | 48 ms (GPU local) |
| M3 SPLADE-PT-BR | esparso aprendido | 0,230 | −0,111 [−0,160; −0,062] | inferior | 22 ms (GPU local) |
| *ablação* RM3 | expansão sem LLM | 0,348 | +0,007 [−0,007; +0,022] | inconclusivo | 6 ms |
| *referência* Nemotron denso puro | ramo denso | 0,386 | +0,044 [+0,002; +0,085] | superior | ~2,0 s |

Detalhes, gráficos e fichas: [reports/c2/RESULTS.md](../../reports/c2/RESULTS.md); análise de erros: [reports/c2/ERRORS.md](../../reports/c2/ERRORS.md).

## Conclusões

1. **O BM25 ajustado é um baseline duro, mas superável em C2 (H2 rejeitada em parte).** Só o híbrido com o embedding Nemotron 3.5 Embed 8B o supera com IC95 fora de zero; três das quatro alternativas ficam significativamente abaixo. Ajustar o BM25 importou: sem stemmer, k1=1,2 e b=0,75, o dev subiu de 0,336 (default do Anserini) para 0,394.
2. **O sinal semântico de um embedding forte ajuda até em consultas de expressão jurídica.** O ramo denso puro (referência) foi o melhor no teste (0,386), e o híbrido aumentou a cobertura (R@100 +0,039, IC fora de zero; H3 apoiada). Na matriz de desacordo, o denso vence o BM25 em 33% das consultas e perde em 20%; o BM25 ganha em referências exatas e termos técnicos (`decreto-lei 4.657/1942`, `patrimônio líquido mínimo`, `mera participação e epp`).
3. **O dev de 30 consultas não tem sinal para escolher o peso da fusão.** Na curva pós-hoc, o dev fica plano (0,375–0,396) de α=0 a α=1, enquanto o teste cresce até α≈0,8 (0,395). A escolha α=0,2 seguiu o protocolo, mas é frágil; o próximo ciclo deve usar validação cruzada no conjunto inteiro ou mais consultas de dev antes de congelar a fusão (H11 continua exploratória: convexa 0,396 × RRF 0,395 no dev).
4. **Expansão por LLM atrapalha C2 (H5 rejeitada para Query2doc).** O pseudodocumento gerado pelo Nemotron Lightning dilui os termos exatos: −0,035, com perdas maiores nas consultas reais e curtas. O RM3, sem LLM, fica neutro. Em C2 a expressão do usuário deve ser preservada.
5. **Os checkpoints esparsos/multilíngues testados não servem para C2 neste corpus sem adaptação (H7 rejeitada).** O SPLADE-PT-BR (domínio geral, mMARCO) dá peso a pontuação e stopwords e perde 0,11; o BGE-M3, truncado em 512 tokens pela GPU de 4 GB, perde 0,06. As duas falhas são, em parte, da configuração possível nesta máquina (checkpoint não jurídico; truncamento), não necessariamente dos métodos.
6. **Consultas reais são o caso difícil.** Em todos os métodos as palavras-chave reais de usuários rendem cerca de metade das sintéticas (BM25 0,19 × 0,49), porque as sintéticas foram geradas dos resumos e herdam o vocabulário dos documentos. Resultados só em consultas sintéticas superestimam a qualidade em produção.

### Recomendação por perfil (C2, este corpus)

| Perfil | Escolha | Por quê |
|---|---|---|
| econômico | M1 BM25 ajustado | 0,341 em 0,25 ms por consulta, CPU, sem modelo nem chave |
| qualidade | M5 híbrido BM25 + Nemotron 8B, com α revisto por validação cruzada | único superior ao BM25 com IC fora de zero; custo dominado por um embedding de consulta por API (gratuito nesta rodada) |
| a evitar em C2 | Query2doc, SPLADE-PT-BR, BGE-M3 truncado | inferiores ao BM25 com IC fora de zero |

### Próximos passos sugeridos

- Validação cruzada da fusão (e do roteamento por tipo de consulta, H12) usando as 100 consultas, antes de abrir um novo teste.
- Repetir no acervo de 370 mil jurisprudências quando ele tiver local: mesmos cinco módulos, formato canônico.
- Testar Nemotron 3.5 Embed 1B (mais barato) no ramo denso e BGE-M3 com documentos inteiros em passagens.
- Coletar mais consultas reais C2 com julgamento jurídico; o teste com 35 reais ainda dá intervalos largos.

## Critérios

Principais: nDCG@10 e Precision@10/20. Complementares: MRR@10, Hit@1, Recall@1/10/20/100, Judged@10, quebras por origem (real/sintética), tamanho, conjunção e digitação sem acento. Latência p50/p95/p99 por etapa, QPS sequencial, RAM/VRAM de pico, bytes de índice, tempo de construção, requisições e tokens de API, custo faturado.

## Limitações conhecidas

- 70 consultas de teste: diferenças menores que ~0,02–0,03 de nDCG@10 tendem a ficar inconclusivas.
- Qrels do JurisTCU julgam 15 documentos por consulta; documentos não julgados contam como não relevantes (Judged@10 reportado).
- Consultas sintéticas (51–100) foram geradas a partir de ENUNCIADOs; o corpus só tem EXCERTO.
- Etiquetas por regra (tamanho, conjunção, sem acento) são auditáveis mas não substituem classificação por dois anotadores.
- Concorrência > 1, atualização incremental e escala acima de 16 mil documentos não foram medidas nesta rodada.
