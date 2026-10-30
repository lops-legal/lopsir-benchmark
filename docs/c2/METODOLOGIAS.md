# C2 — fichas das cinco metodologias

Formato do [pipeline comum](../PIPELINE.md): método original → implementação pública → adaptação ao jurídico → experimento local → resultado observado. Os números de resultado ficam em [reports/c2/RESULTS.md](../../reports/c2/RESULTS.md), gerado a partir de `reports/c2/<método>/result.json`; esta ficha descreve o que foi executado.

## Dados e protocolo comuns aos cinco

| Item | Valor |
|---|---|
| Base | Repositório `lops-legal/lopsir-benchmark` (contratos, avaliador, código) — sem corpus próprio ainda; o acervo de ~370 mil jurisprudências não tem local definido |
| Dados reais | JurisTCU `ufca-llms/juris-tcu`, revisão `05f66e126f4375962a73cfd58db2c73a2945b9ef`, só `EXCERTO` (16.045 documentos, ~4.387 caracteres em média) — autorizado pelo usuário em 29/10/2026 ("base do repo e depois JurisTCU se for facilmente baixável") |
| Consultas C2 | ids 1–50 (palavras-chave reais de usuários) e 51–100 (palavras-chave sintéticas); 101–150 são perguntas → C3, excluídas |
| Qrels | graus 0–3 originais; relevante binário = grau ≥ 1; nDCG com ganho linear |
| Split | dev 30 / teste 70, estratificado por origem, grupos de quase-duplicatas, semente 42, congelado antes de qualquer ajuste ([manifesto](../../reports/c2/dataset-juristcu.json), [etiquetas](../../reports/c2/queries-juristcu.tsv)) |
| Seleção | cada método ajusta seus parâmetros só no dev pela nDCG@10; a configuração vencedora roda uma vez no teste |
| Avaliador | `scripts/evaluate.py` compartilhado com C1 (mesmas convenções); cortes 1/10/20/100 |
| Incerteza | bootstrap pareado por grupo de consulta, 10.000 reamostragens; veredito contra o BM25 só fora de zero |
| Latência | aquecimento com as consultas do dev; métodos locais: 5 rodadas no teste; métodos com API: 1º passe paga a chamada real (registrado à parte) |
| Máquina | GTX 1650 4 GB (fp16 mediu 5× mais lento que fp32 nesta placa), ~7,8 GB RAM, 12 threads, Windows |
| Chaves | só no `.env` ignorado pelo Git; nenhum custo faturado (modelos gratuitos) |

## M1 — BM25 ajustado · *mais barata*

1. **Método original:** BM25, Robertson & Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond* ([doi:10.1561/1500000019](https://doi.org/10.1561/1500000019)).
2. **Implementação pública:** [xhluca/bm25s](https://github.com/xhluca/bm25s) 0.3.16 ([arXiv:2407.03618](https://arxiv.org/abs/2407.03618)), `method="lucene"` — a fórmula do Lucene/Anserini, que é o baseline `bm25/anserini` do JUÁ. Pyserini não foi usado porque a máquina não tem Java; desvio registrado.
3. **Adaptação:** analisador próprio em português que mantém números jurídicos inteiros (`4.657/1942`), stopwords PT, Snowball português (PyStemmer 3.1.0) opcional e remoção de acentos opcional — aplicada **antes** do stemmer para casar digitação sem acento.
4. **Experimento:** 4 analisadores × k1 {0,6; 0,9; 1,2; 1,5; 1,8} × b {0,2; 0,4; 0,6; 0,75; 0,9; 1,0} + default Anserini (k1 0,9, b 0,4) = 121 configurações no dev. CPU, sem modelo, sem chave.
5. **Módulo:** `python -m lopsir_c2.m1_bm25`.

## M2 — Query2doc · *expansão por LLM* (ablação: RM3, *expansão sem LLM*)

1. **Método original:** Query2doc, Wang, Yang & Wei ([arXiv:2303.07678](https://arxiv.org/abs/2303.07678)): um LLM escreve um pseudodocumento; para recuperação esparsa a consulta é repetida *n* vezes e concatenada ao pseudodocumento.
2. **Implementação pública:** o artigo não publicou repositório oficial (só existem demos de terceiros). Implementado a partir do artigo sobre o BM25 congelado do M1 (bm25s). Isso é um desvio do critério "GitHub público" e está declarado.
3. **Modelo e API:** `nvidia/nemotron-3.5-lightning:free` via OpenRouter (`POST /api/v1/chat/completions`, chave `OPENROUTER_API_KEY`), raciocínio desligado (com raciocínio o orçamento curto voltava vazio), temperatura 0 (o artigo amostra), 128 tokens novos como no artigo. Expansões ficam em cache e são reaproveitadas.
4. **Adaptação:** prompt em português pedindo um trecho de jurisprudência do TCU; zero-shot ou 4 exemplos *só do dev* (consulta + 600 caracteres de um documento grau 3; uma consulta do dev nunca vê a si mesma); BM25 não reajustado.
5. **Experimento:** prompt {zero, few4} × n {3, 5} no dev.
6. **Ablação identificada RM3:** Abdul-Jaleel et al., UMass/TREC 2004 ([pdf](https://ciir.cs.umass.edu/pubfiles/ir-338.pdf)); implementação de referência [castorini/anserini](https://github.com/castorini/anserini) (Pyserini, [arXiv:2102.10073](https://arxiv.org/abs/2102.10073)). Reimplementado em Python sobre o BM25 do M1: fbDocs {5, 10, 20} × fbTerms {10, 20, 30} × peso original {0,3; 0,5; 0,7}. Sem LLM, sem rede. Mede o ganho atribuível ao LLM.
7. **Módulo:** `python -m lopsir_c2.m2_expansion` (`--only rm3|q2d`).

## M3 — SPLADE esparso aprendido · *mais precisa no paradigma lexical*

1. **Método original:** SPLADE v2, Formal et al. ([arXiv:2109.10086](https://arxiv.org/abs/2109.10086)); relatório SPLADE-v3 ([arXiv:2403.06789](https://arxiv.org/abs/2403.06789)). Pesos `max_i log(1 + ReLU(logit MLM))` sobre o vocabulário, regularização FLOPS, produto escalar em índice invertido.
2. **Implementação pública:** framework [naver/splade](https://github.com/naver/splade); checkpoint em português [AxelPCG/splade-pt-br](https://huggingface.co/AxelPCG/splade-pt-br) (código [AxelPCG/SPLADE-PT-BR](https://github.com/AxelPCG/SPLADE-PT-BR)), revisão `b44dd3d0336b5c386cccb5e76608348386768745`, Apache-2.0: BERTimbau base treinado no mMARCO-pt com a receita naver/splade, comprimento máximo 256.
3. **Adaptação:** os pesos são carregados direto num `BertForMaskedLM` (sem executar código remoto) e o pooling SPLADE é reimplementado como no `modeling_splade.py` do checkpoint. Documentos (~1,5 mil tokens) são cortados em janelas de 254 tokens (75.135 passagens); o escore do documento é MaxP (máximo entre passagens) ou FirstP, escolhido no dev. Índice CSC (scipy).
4. **Riscos registrados:** checkpoint de domínio geral, não jurídico; na inspeção, a consulta "novo e improrrogável prazo" recebeu os maiores pesos em pontuação e stopwords (`,`, `e`, `de`), sinal de calibração fraca.
5. **Execução:** GPU local em fp32, pooling in-place (cabe em ~0,9 GB de VRAM), sem API.
6. **Módulo:** `python -m lopsir_c2.m3_splade`.

## M4 — BGE-M3 · *modelo único multilíngue*

1. **Método original:** M3-Embedding, Chen et al. ([arXiv:2402.03216](https://arxiv.org/abs/2402.03216)): um único modelo produz vetor denso, pesos lexicais esparsos e multivetor; a recuperação híbrida soma os escores ponderados.
2. **Implementação pública:** [FlagOpen/FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) 1.4.2 (`BGEM3FlagModel`); checkpoint [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3), revisão `5617a9f61b028005a4858fdac845db406aefb181`, MIT, XLM-RoBERTa large (568M parâmetros).
3. **Adaptação:** denso + pesos lexicais numa única passada; modos denso, esparso e denso+esparso com peso do esparso {0,05; 0,1; 0,2; 0,3; 0,5} escolhidos no dev. A cabeça ColBERT ficou de fora: os vetores por token do corpus excedem o orçamento de disco/RAM (desvio registrado). Documentos truncados em `--max-length` tokens.
4. **Execução:** GPU local fp32, sem API; latência mede a codificação da consulta em toda chamada.
5. **Módulo:** `python -m lopsir_c2.m4_bgem3`.

## M5 — Híbrido BM25 + denso com fusão ajustada · *junta tudo*

1. **Método original:** Bruch, Gai & Ingber, *An Analysis of Fusion Functions for Hybrid Retrieval* ([arXiv:2210.11934](https://arxiv.org/abs/2210.11934)): RRF contra combinação convexa de escores normalizados.
2. **Implementação pública:** as duas funções de fusão estão em [AmenRa/ranx](https://github.com/AmenRa/ranx); foram reimplementadas conforme o artigo (RRF; convexa min-max) e testadas à mão em `tests/test_c2.py`.
3. **Ramos:** lexical = BM25 congelado do M1; denso = `nvidia/nemotron-3.5-embed-8b` (4.096 dimensões) pela API gratuita da NVIDIA (`POST https://integrate.api.nvidia.com/v1/embeddings`, chave `NVIDIA_API_KEY`, `input_type` query/passage, `truncate=END`), com busca **exata** por cosseno sobre o corpus inteiro (sem erro de ANN).
4. **Experimento:** RRF k {10, 60, 100} × profundidade {100, 1000}; convexa α {0,1…0,9} com profundidade 1000 — 15 configurações no dev.
5. **Referência identificada:** o ramo denso sozinho (`m5_dense_reference`), para atribuir o ganho da fusão.
6. **Módulos:** `python -m lopsir_c2.m5_hybrid.encode` (vetores, retomável) e `python -m lopsir_c2.m5_hybrid`.

## Modelos gratuitos verificados em 29/10/2026

| Uso | Modelo | Provedor | Situação |
|---|---|---|---|
| Embedding denso | `nvidia/nemotron-3.5-embed-8b` (4.096-d) | NVIDIA API Catalog | ✅ escolhido (melhor modelo gratuito disponível) |
| Embedding denso | `nvidia/nemotron-3.5-embed-1b` (2.048-d) | NVIDIA | ✅ disponível, não usado |
| Embedding denso | `nvidia/nemotron-3.5-embed-8b:free` | OpenRouter | ✅ reserva; não misturado com o da NVIDIA |
| LLM de expansão | `nvidia/nemotron-3.5-lightning:free` | OpenRouter | ✅ escolhido (2,6 s, custo 0, raciocínio desligado) |
| LLM | `google/gemma-4-31b-it` | NVIDIA | ⚠️ respondeu, mas ficou ~4 min na fila |
| LLM | `nvidia/nemotron-3-super-120b-a12b` | NVIDIA | ❌ 404 nesta conta |
| Reranqueadores | `llama-3.2-nv-rerankqa-1b-v2`, `nemoretriever-500m-rerank-v2` | NVIDIA | ❌ fim de vida (HTTP 410) |
| Embedding | `qwen/qwen3-embedding-8b`, `baai/bge-m3` | OpenRouter | pagos (centavos); não usados — BGE-M3 roda local |
