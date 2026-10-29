# Pipeline de pesquisa — C1 → C2 → C3

Estado em 29/10/2026: planejamento de C1. O usuário informa um acervo de aproximadamente **370 mil jurisprudências reais**. A localização e o esquema desse acervo ainda precisam ser ligados ao pipeline. Não gerar dados fictícios, importar outra coleção ou declarar resultados enquanto isso não estiver resolvido.

## 1. Unidade de comparação: metodologia, no nível do JUÁ

Cada linha principal do estudo identifica uma metodologia publicada, sua implementação pública e os componentes realmente usados. Bancos são parâmetros de implementação ou uma comparação de sistemas à parte. Não comparar `BERT`, `BM25`, `pgvector` e `Parquet` como categorias do mesmo nível.

Por C, selecionar **cinco metodologias** fundamentadas em artigo e código público. A seleção deve cobrir vantagens diferentes como custo, qualidade, robustez e equilíbrio; essas vantagens são hipóteses, não resultados antecipados. Não criar uma fórmula de ranking nova e apresentá-la como método da literatura.

Toda ficha deve separar:

1. Método original: nome, artigo/DOI/arXiv, tarefa e contribuição.
2. Implementação pública: GitHub, commit/tag e dependências.
3. Adaptação ao jurídico: entradas, campos, normalização e diferenças em relação ao artigo.
4. Experimento local: dados e splits, parâmetros, métricas, recursos e limites.
5. Resultado observado: ranking, intervalos, latência, custo, falhas e conclusão.

Estado explícito: `proposed → sources_verified → input_ready → implementation_ready → smoke_passed → dev_frozen → evaluated → reviewed`. Um artigo verificado não significa que o adaptador foi implementado. Um teste unitário não é um benchmark jurídico.

## 2. Definições sem sobreposição artificial

| Caso | Intenção | Alvo | Não confundir com |
|---|---|---|---|
| C1 | Localizar uma identidade explicitamente referenciada | Documento/processo/acórdão identificado, ou conjunto legítimo de identidades | Documentos que discutem assunto parecido ou apenas citam o alvo |
| C2 | Pesquisar expressão jurídica, palavras-chave ou trecho | Documentos pertinentes aos termos e à intenção | Localizar um identificador conhecido |
| C3 | Pesquisar uma questão ou problema descrito | Documentos/fundamentos pertinentes aos fatos e à questão | Similaridade textual sem pertinência jurídica |

Uma pergunta com um número de tema pode continuar C3 se pedir como a tese se aplica aos fatos. Uma referência curta pode ser C1 mesmo sem frase completa. Registrar casos mistos; não classificar por tamanho ou pontuação apenas.

## 3. Onde o JUÁ se encaixa

O JUÁ é um benchmark de recuperação heterogênea, não uma categoria C. Nossa leitura da tarefa de cada coleção indica:

| Coleção | Enquadramento inicial | Observação |
|---|---|---|
| JUÁ-Juris | Principalmente C3 | Enunciado jurídico procura excerto de sustentação; consulta abstrativa, não necessariamente relato fático real |
| JurisTCU | C2 e C3 | Palavras-chave reais/sintéticas e perguntas sintéticas; revisar cada consulta |
| NormasTCU | C2 e C3 | Consultas curtas e consultas mais elaboradas |
| Ulysses-RFCorpus | Principalmente C3, com revisão para C2 | Pedidos legislativos operacionais |
| BR-TaxQA | Principalmente C3 | Perguntas procuram respostas e referências |

Essa classificação é uma extensão analítica nossa. Não é uma etiqueta publicada pelo JUÁ e não deve ser aplicada em bloco sem revisar as consultas. O JUÁ não fornece uma trilha específica equivalente ao nosso C1 de identidade.

Fonte: [JUÁ v2](https://arxiv.org/abs/2604.06098v2), seções 3–5. JurisTCU original também possui grupos de formulação, mas seus G1/G2/G3 não são nossos C1/C2/C3: [artigo](https://arxiv.org/abs/2503.08379).

## 4. Ordem e gates

### G0 — inventário real

- Localizar o acervo fornecido pelo usuário, sem acrescentar datasets.
- Registrar caminho/conexão, formato, revisão/snapshot, hash quando aplicável e contagem real.
- Confirmar quais campos identificam documento, processo e decisão; detectar versões e duplicatas.
- Conferir as permissões de leitura e as condições de redistribuição. Dados grandes e credenciais não entram no Git.
- A contagem 370 mil é informação do usuário até a leitura do acervo; não registrá-la como contagem verificada.

### G1 — C1

- Aplicar o protocolo em [c1/README.md](c1/README.md).
- Selecionar cinco métodos e seus parâmetros em desenvolvimento.
- Usar referências e identidades reais, verificadas no acervo.
- Concluir os cinco relatórios, incluindo método que falhou ou ficou inviável.
- Revisar erros de identidade e ambiguidades; publicar conclusão e limitações.

### G2 — C2

- Começar execução depois da revisão de C1.
- Usar o mesmo acervo permitido, mas consultas e qrels próprios para expressão jurídica.
- Não reutilizar os positivos de identidade C1 como relevância temática.
- Selecionar e detalhar cinco métodos conforme [c2/README.md](c2/README.md).

### G3 — C3

- Começar execução depois da revisão de C2.
- Usar problemas/perguntas e julgamentos pertinentes aos fatos e fundamentos.
- Selecionar e detalhar cinco métodos conforme [c3/README.md](c3/README.md).

A preparação documental das próximas etapas pode ocorrer em paralelo. A execução e a publicação de conclusões continuam sequenciais. A branch de reprodução [jua/README.md](jua/README.md) é um controle separado, condicionado aos artefatos existentes/indicados no próprio projeto; não autoriza baixar novas coleções.

## 5. Relatório obrigatório de cada metodologia

| Grupo | Campos obrigatórios |
|---|---|
| Evidência | Artigo, GitHub, revisão, natureza da adaptação e estado do adaptador |
| Dados | Snapshot, unidade avaliada, consultas, qrels, splits, exclusões e origem das perguntas |
| Qualidade comum | Hit@1, MRR@10, nDCG@10, Precision@10/20 e Recall@20/100, quando definidos |
| Qualidade por caso | C1: identidade/ambiguidade/ausência; C2/C3: pertinência e cobertura dos julgamentos |
| Rapidez | p50/p95/p99 ponta a ponta, etapas, QPS, concorrência, fila, erros e timeout |
| Recursos | Pico de RAM/VRAM, bytes do índice e tempo de preparação/construção |
| Custos | Ingestão, consulta, API, armazenamento e hipóteses monetárias declaradas |
| Atualização | Inserção, exclusão, tempo até pesquisável e consistência do snapshot |
| Conclusão | Diferença contra baseline, incerteza, erros e perfil de uso recomendado ou inconclusivo |

Métrica não aplicável deve ser `null` com justificativa, nunca zero inventado. Uma chamada de API não realizada não produz custo ou latência observados. O custo local não é considerado zero: guardar recursos físicos e, se estimado em moeda, declarar energia e amortização.

## 6. Regras de justiça experimental

- Cinco métodos usam o mesmo snapshot e conjunto de teste dentro do mesmo C.
- Consultas reais e transformações controladas têm origens distintas e resultados separados. Nesta fase não criar transformações nem consultas artificiais sem autorização específica.
- Escolher configurações no dev, congelar e só então avaliar o teste.
- Agrupar splits e intervalos por identidade/decisão para evitar variantes do mesmo alvo em lados opostos.
- Preservar unidade documental e graus originais; colapsar passagens no pai antes de avaliar decisões.
- Reportar erros e falhas de todos os métodos, não apenas as execuções concluídas com sucesso.
- Não trocar o método ou o banco para mascarar um adaptador que não ficou pronto.
- Um resultado local não demonstra comportamento em bilhões de documentos.

## 7. Branches e colaboração

| Branch | Responsabilidade | Escopo |
|---|---|---|
| `c1` | Trabalho ativo desta etapa | Protocolo, cinco fichas, contratos e futura execução de C1 |
| `c2` | Claude — executado em 29/10/2026 | Cinco metodologias implementadas e avaliadas sobre o JurisTCU por instrução do usuário (o acervo de 370 mil ainda sem local); ver [c2/README.md](c2/README.md) e `reports/c2/RESULTS.md`. Revisão pendente antes de integrar à `main` |
| `c3` | Preparação futura | Especificação/implementação C3; execução após gate de C2 |
| `jua` | Reprodução científica separada | Protocolo nativo JUÁ e compatibilidade dos avaliadores |
| `main` | Base publicada | Mudanças integradas e revisadas |

Commits por entrega verificável. Nunca publicar credenciais, emails pessoais em documentação, índices, dados grandes ou resultados simulados. Não fazer force-push nem substituir trabalho de outro colaborador. Os contratos comuns têm um commit-base compartilhado; alterações posteriores devem ser integradas explicitamente para evitar divergência.

## 8. O que é necessário agora

1. Caminho ou conexão das 370 mil jurisprudências e descrição dos campos disponíveis.
2. Referências/consultas C1 reais já disponíveis, ou autorização específica para construir uma suíte derivada de identidades reais. Não confundir derivação de metadados com consulta real de usuário.
3. Confirmação dos objetivos: localizar documento, acórdão ou processo; essa informação pode vir do próprio esquema e das consultas existentes.

Nenhuma chave de Qwen, Nemotron, OpenRouter ou GPU é requisito dos cinco métodos C1 selecionados. Futuras APIs em C2/C3 serão descritas antes de qualquer gasto. PDFs não precisam ser solicitados ao usuário enquanto as fontes primárias já forem acessíveis.

Este arquivo atualiza a ordem operacional do SDD original. A pesquisa ampla continua como referência, mas qualquer roteiro que comece por C3/BR-TaxQA ou pela importação de outras coleções está suspenso pela instrução mais recente: **C1 primeiro, dados reais do projeto, cinco métodos por caso**.
