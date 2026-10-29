# LopsIR Benchmark

Estudo de arquiteturas de recuperação jurídica por tipo de consulta: **C1 referência exata, C2 expressão jurídica e C3 problema em linguagem natural**.

Leia [a especificação completa](SDD-PESQUISA.md): escopo, leitura integral do JUÁ v2, métricas explicadas, hipóteses H1–H16, benchmarks reais, parâmetros, arquitetura, controles de custo e backlog.

## Estado da entrega

Documentação e kit mínimo executável. **Nenhum banco, modelo ou benchmark real foi executado.** Adaptadores, importadores e interface do hub estão especificados para implementação incremental. `reports/fixture-metrics.json` é apenas uma demonstração com quatro consultas artificiais; não entra no leaderboard científico.

## Começar sem dependências externas

Na raiz desta pasta, com Python 3.11+:

```powershell
python scripts/doctor.py --output reports/environment.json
python -m unittest discover -s tests -v
python scripts/evaluate.py --queries examples/queries.jsonl --qrels examples/qrels.tsv --run examples/run.tsv --cutoffs 10 20 100 --output reports/fixture-metrics.json
```

Os três scripts usam somente a biblioteca padrão. O diagnóstico informa o que conseguiu detectar e o que ficou indisponível; não instala serviços nem chama APIs. O avaliador rejeita IDs desconhecidos, rankings duplicados e dados inválidos. Avalia também consultas elegíveis que não retornaram resultados, com score zero.

**Exemplo de Recall@20:** de 10 documentos relevantes conhecidos, recuperamos 6 entre os primeiros 20: recall de 60%. A precisão da mesma lista é 6/20 = 30%.

A fixture é ilustrativa e usa IDs fictícios `demo-*`. O avaliador do kit adota nDCG com ganho linear; antes do uso científico, conferir equivalência com o avaliador oficial do benchmark. A convenção de AP está explícita no SDD e nos nomes de saída.

## Próximo ciclo implementável

1. Criar `.venv` própria e fixar dependências; consultar a seção operacional única do SDD.
2. Importar BR-TaxQA e JurisTCU em revisões fixadas e verificar corpus, queries e qrels.
3. Implementar BM25 de referência e suíte C1 com metadados reais.
4. Adicionar um embedding, scoring exato, um motor vetorial e fusão.
5. Medir por caso e coleção; só então ampliar bancos e modelos.

`configs/experiment.example.json` demonstra o contrato de planejamento. Não é configuração de um runner já implementado. Seu campo `status: planned` e os campos nulos impedem confundir exemplo com experimento reproduzido.

## Repositório e autoria

Destino: [lops-legal/lopsir-benchmark](https://github.com/lops-legal/lopsir-benchmark). Projeto **LopsIR Benchmark**, com histórico organizado por entregas: base do projeto, metodologia, configuração de experimentos, avaliação de rankings e diagnóstico local.

Email de autoria dos commits: `lucascardososilva@usp.br`. Dados, índices, credenciais e PDF não fazem parte do repositório. A escolha de licença do projeto permanece pendente; as licenças dos datasets e modelos devem ser registradas separadamente na ingestão. Veja [os avisos de fontes](NOTICE.md).
