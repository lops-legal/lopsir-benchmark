# Fontes e estado dos artefatos

LopsIR Benchmark é um projeto de pesquisa de arquiteturas de recuperação jurídica. O documento SDD-PESQUISA.md reúne referências primárias e distingue resultados publicados, hipóteses do projeto e resultados locais ainda não produzidos.

## Fontes de terceiros

- JUÁ v2: [arXiv:2604.06098v2](https://arxiv.org/abs/2604.06098v2). A documentação registra o hash do PDF analisado; o PDF não é redistribuído.
- Os datasets, modelos e motores citados não estão incluídos neste repositório. Suas condições de uso e revisões devem ser verificadas antes da importação ou distribuição.
- O nome LopsIR Benchmark identifica este estudo; não implica afiliação com os autores dos artigos, tribunais ou fornecedores citados.

### Usados na execução do C2 (branch `c2`)

- JurisTCU adaptado ao JUÁ: [ufca-llms/juris-tcu](https://huggingface.co/datasets/ufca-llms/juris-tcu), revisão `05f66e126f4375962a73cfd58db2c73a2945b9ef`. O cartão do dataset não declara licença. Corpus, consultas e qrels **não** são versionados: ficam em `data/` (ignorado) e o repositório guarda só hashes, contagens, ids, etiquetas, rankings de ids e métricas. `reports/c2/ERRORS.md` cita o texto de consultas de teste (palavras-chave curtas) para a análise de erros; nenhum trecho de documento é reproduzido.
- Checkpoints baixados para execução local (não versionados, em `artifacts/`): [AxelPCG/splade-pt-br](https://huggingface.co/AxelPCG/splade-pt-br) (Apache-2.0) e [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) (MIT).
- Modelos por API gratuita: `nvidia/nemotron-3.5-embed-8b` e `nvidia/nemotron-3.5-lightning-30b-a3b` (NVIDIA API Catalog), sujeitos aos termos de cada provedor. Os vetores e as expansões gerados ficam fora do Git.

## Artefatos próprios e reprodução

As consultas e IDs em `examples/` são uma fixture artificial criada para conferir métricas; não são decisões reais nem benchmark jurídico. O relatório `reports/fixture-metrics.json` não deve ser citado como evidência de desempenho de modelos.

`reports/environment.json` registra um diagnóstico de uma máquina e de um interpretador em uma data; não garante disponibilidade futura de recursos ou software.

A licença do projeto ainda não foi escolhida. Esta publicação não acrescenta uma licença aos materiais de terceiros referenciados.
