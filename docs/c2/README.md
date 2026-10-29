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

## Critérios

Principais: nDCG@10 e Precision@10/20. Complementares: MRR@10, Hit@1, Recall@1/10/20/100, Judged@10, quebras por origem (real/sintética), tamanho, conjunção e digitação sem acento. Latência p50/p95/p99 por etapa, QPS sequencial, RAM/VRAM de pico, bytes de índice, tempo de construção, requisições e tokens de API, custo faturado.

## Limitações conhecidas

- 70 consultas de teste: diferenças menores que ~0,02–0,03 de nDCG@10 tendem a ficar inconclusivas.
- Qrels do JurisTCU julgam 15 documentos por consulta; documentos não julgados contam como não relevantes (Judged@10 reportado).
- Consultas sintéticas (51–100) foram geradas a partir de ENUNCIADOs; o corpus só tem EXCERTO.
- Etiquetas por regra (tamanho, conjunção, sem acento) são auditáveis mas não substituem classificação por dois anotadores.
- Concorrência > 1, atualização incremental e escala acima de 16 mil documentos não foram medidas nesta rodada.
