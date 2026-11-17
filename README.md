# LopsIR Benchmark

Estudo de arquiteturas de recuperação jurídica por tipo de consulta: **C1 referência exata, C2 expressão jurídica e C3 problema em linguagem natural**.

Leia [a especificação completa](SDD-PESQUISA.md): escopo, leitura integral do JUÁ v2, métricas explicadas, hipóteses H1–H16, benchmarks reais, parâmetros, arquitetura, controles de custo e backlog.

**Plano operacional atual:** [C1 → C2 → C3](docs/PIPELINE.md), com cinco metodologias publicadas por caso. O acervo real foi localizado em [leis-mcp](https://github.com/lops-legal/leis-mcp): 347.195 dispositivos legais e 11.253 precedentes. Não usar informações fictícias nos experimentos nem importar novos conjuntos. A [reprodução do JUÁ](docs/jua/README.md) é uma trilha separada.

## Estado da entrega

**C1 executado sobre o acervo real:** PostgreSQL 18, 341.827 identidades distintas, cinco métodos, 305 consultas de teste por método e três repetições. [Resultados, gráficos e limites](reports/c1/real/README.md) · [reprodução local](docs/c1/EXECUCAO.md). As consultas são sete chamadas existentes na fonte e 298 referências derivadas de metadados reais, sem histórias ou referências fictícias. Este teste mede identidade íntegra; não mede relevância semântica nem robustez a erros de digitação.

![Comparação real de C1](reports/c1/real/figures/comparison.png)

Os exemplos antigos e `reports/fixture-metrics.json` são somente testes históricos do avaliador; não entram no estudo real. C2 pertence a outra frente de trabalho; esta branch implementa exclusivamente C1.

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

1. Revisar o inventário e os hashes reais em [corpus-manifest.json](reports/c1/real/corpus-manifest.json).
2. Revisar [C1](docs/c1/README.md): cinco métodos implementados e resultados por consulta.
3. Ampliar C1 com consultas reais difíceis quando disponíveis; coordenar a revisão com a frente [C2](docs/c2/README.md).
4. Executar e revisar C2 antes dos experimentos [C3](docs/c3/README.md).
5. Preservar a trilha JUÁ separadamente, usando apenas os artefatos disponibilizados/indicados no projeto.

`configs/experiment.example.json` demonstra o contrato de planejamento. Não é configuração de um runner já implementado. Seu campo `status: planned` e os campos nulos impedem confundir exemplo com experimento reproduzido.

## Repositório e autoria

Destino: [lops-legal/lopsir-benchmark](https://github.com/lops-legal/lopsir-benchmark). Projeto **LopsIR Benchmark**, com histórico organizado por entregas: base do projeto, metodologia, configuração de experimentos, avaliação de rankings e diagnóstico local.

Dados, índices, credenciais e PDF não fazem parte do repositório. A escolha de licença do projeto permanece pendente; as licenças dos datasets e modelos devem ser registradas separadamente na ingestão. Veja [os avisos de fontes](NOTICE.md).
