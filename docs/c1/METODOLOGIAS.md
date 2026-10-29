# C1 — cinco metodologias, referências e protocolo de execução

Versão 0.2 — 29/10/2026. Os cinco métodos foram implementados e executados no acervo real de [leis-mcp](https://github.com/lops-legal/leis-mcp). [Protocolo realmente executado](EXECUCAO.md) e [resultados medidos](../../reports/c1/real/README.md) distinguem parâmetros fixos usados nesta rodada das grades de desenvolvimento ainda propostas abaixo. Nenhum dado fictício ou outra coleção foi usado.

## 1. Escopo da tarefa

**Intenção:** localizar a identidade referenciada, mesmo que sua expressão textual varie. **Unidade:** documento, acórdão ou processo, definida pelo esquema real e pela intenção da consulta. **Verdade de referência:** identidades corretas/compatíveis, verificadas nos dados. **Não é C1:** encontrar uma tese semelhante, localizar fundamentos para fatos ou retornar qualquer texto que cite a referência.

A representação comum é um registro de identidade: identificador interno + referência original + campos identificadores existentes. Exemplos de campos lógicos são instituição, tipo, número, ano, órgão e versão; nenhum deles será preenchido com valor inventado. Esses nomes são um contrato lógico, não uma afirmação sobre o esquema do acervo.

Não usar ementa/inteiro teor como substituto de identidade neste primeiro estudo. Isso favoreceria documentos que apenas citam outro processo e misturaria C1 com busca temática. Um futuro experimento de extração de referência do corpo terá sua própria etapa, custo e avaliação.

## 2. Seleção dos cinco métodos

| ID | Método | Hipótese de vantagem | Limite importante |
|---|---|---|---|
| C1-M1 | Igualdade em chave composta com B-tree | Simplicidade, precisão e baixo custo na referência íntegra | Não corrige erro de digitação; não resolve falta de campos |
| C1-M2 | BM25 sobre referências e campos identificadores | Recuperação lexical de expressões de referência em ordem variável | Pontuação lexical não prova identidade |
| C1-M3 | Similaridade por trigramas indexados | Tolerância a pequenas variações de caracteres | Strings numéricas próximas podem designar objetos distintos |
| C1-M4 | Distância de edição Levenshtein | Tolerância explícita e interpretável a inserção/remoção/substituição | Custo de comparar muitos candidatos; risco de falso match |
| C1-M5 | Fellegi–Sunter para vinculação probabilística | Combinar evidências de campos incompletos ou divergentes | Exige estimação, validação e candidatos adequados |

As cinco famílias existem na literatura. O uso em referências jurídicas é a adaptação a testar. Não se afirma que um artigo publicou exatamente nossa combinação de campos ou que estes sejam cinco campeões SOTA de busca semântica. C1 é uma tarefa de identidade: aplicar embeddings/SPLADE/GraphRAG como obrigação metodológica confundiria a pergunta. Essas famílias ficam nos planos C2/C3.

## 3. Ficha C1-M1 — igualdade em chave composta com B-tree

**Fundamento:** Bayer e McCreight, *Organization and maintenance of large ordered indexes*, 1972. [Artigo/DOI](https://doi.org/10.1007/BF00288683). O artigo fundamenta B-trees; não é um estudo jurídico.

**Implementação pública:** [PostgreSQL](https://github.com/postgres/postgres). [Documentação de índices](https://www.postgresql.org/docs/18/indexes-types.html) confirma igualdade e intervalos com B-tree. A implementação moderna de PostgreSQL não é apresentada como reprodução binária do programa do paper de 1972.

**Arquitetura:** consulta → extração/normalização de campos → predicado de igualdade sobre campos efetivamente informados → índice → conjunto de identidades. Normalização e extração são adaptações nossas, compartilhadas e avaliadas separadamente.

**Entrada indexada:** somente identidade e aliases aprovados que constem da fonte. Chave composta deve ser descoberta pelo inventário; não impor unicidade a número/ano se houver distinção por órgão, tipo ou versão.

**Saída:** zero identidades, identidade única ou conjunto ambíguo. Campos omitidos não recebem valor padrão. Igualdade não produz uma probabilidade nem um score semântico. Empates de identidade não são desfeitos por popularidade ou data sem critério explícito; o conjunto é devolvido como ambíguo.

**Dependências:** servidor PostgreSQL, cliente Python `psycopg`, biblioteca padrão para parsing. Não requer pgvector, modelo, GPU ou API. Versão estável de servidor/cliente será congelada no ambiente real; o commit upstream inspecionado é evidência de fonte, não lockfile de execução.

**Parâmetros:** colunas/ordem do índice; aliases; collation; política de normalização; limite de resultados; timeout; pool de conexões. Estrutura e regras são congeladas em dev. Comparar ingestão/construção e atualização, além de consultas. Examinar `EXPLAIN` para confirmar acesso real pelo índice.

**Critério específico:** Hit@1 no subconjunto inequívoco, correção de conjunto nos ambíguos, taxa de rejeição em alvos ausentes do snapshot e colisões introduzidas pela normalização. Não chamá-lo de mais barato até medir.

## 4. Ficha C1-M2 — BM25 lexical

**Fundamento e implementação desta rodada:** Lù, *BM25S: Orders of magnitude faster lexical search via eager sparse scoring*, 2024. [arXiv:2407.03618](https://arxiv.org/abs/2407.03618). Para a formulação BM25: Robertson e Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond*, [DOI](https://doi.org/10.1561/1500000019).

**Implementação pública executada:** [xhluca/bm25s](https://github.com/xhluca/bm25s), versão 0.3.16, variante `lucene`, backend NumPy. A proposta inicial era [Pyserini](https://github.com/castorini/pyserini), [artigo](https://arxiv.org/abs/2102.10073). A troca foi registrada para evitar Java e dependências neurais desnecessárias nesta máquina de 8 GB; continua sendo BM25, com implementação diferente explicitamente identificada. Não alegar ter executado Pyserini/Lucene.

**Arquitetura:** consulta de referência → tokenização controlada → índice invertido de referências → BM25 → candidatos de identidade. O texto indexado é a serialização determinística dos campos permitidos. Não indexar temas ou excertos e depois alegar que o ganho é resolução de identidade.

**Adaptação:** preservar grupos numéricos e termos de órgão/tipo; sem stemming de identificadores; documentar segmentação de pontuação. Comparar entrada original com entrada normalizada como ablação, mantendo o mesmo pipeline de parsing quando aplicável. A referência a outro documento dentro de um excerto não se torna identidade do excerto.

**Dependências executadas:** BM25S, NumPy e SciPy, com versões em `requirements-c1.lock.txt`. Não usa Java, PyJNIus, modelo neural ou API. Nesta rodada: k1=1,2; b=0,75; sem stemming/stopwords; um thread de recuperação; top-100. A grade abaixo permanece uma hipótese futura, não foi ajustada olhando o teste.

**Modelos/chaves:** nenhum embedding, nenhuma chave. A presença de cliente de API nas dependências do toolkit não implica chamada remota de BM25.

**Parâmetros de exploração propostos:** k1 em {0,6; 1,2; 1,8}, b em {0,2; 0,75; 1}; top-k em {10; 20; 100}; uma análise linguística inicial fixa. Essa grade é proposta por nós, não uma configuração reproduzida do JUÁ. O número de tentativas é controlado no dev.

**Rejeição:** BM25 sempre pode produzir algum ranking. Seu score não é probabilidade. Limiar e margem de abstenção, se usados, serão calibrados somente no dev e relatados separados do ranking puro.

**Critério específico:** verificar se ordem variável e palavras de apresentação ajudam sem aumentar erros entre números/anos/órgãos próximos. Medir candidatos corretos antes da decisão final.

## 5. Ficha C1-M3 — trigramas indexados

**Fundamento de família:** Ukkonen, *Approximate string-matching with q-grams and maximal matches*, 1992. [Artigo/DOI](https://doi.org/10.1016/0304-3975(92)90143-4). O paper é fundamento de matching por q-grams; não afirma que a função `similarity` de PostgreSQL seja o mesmo algoritmo ou a mesma distância formal do artigo.

**Implementação pública escolhida:** extensão [pg_trgm no PostgreSQL](https://github.com/postgres/postgres/tree/master/contrib/pg_trgm). A [documentação oficial](https://www.postgresql.org/docs/18/pgtrgm.html) é a referência para semântica de trigramas, operadores e índices desta execução. Precisamos dos dois vínculos: fundamento acadêmico da família e especificação efetiva do código usado.

**Arquitetura:** referência normalizada → string canônica → trigramas → recuperação indexada → ranking por similaridade de caracteres. Utilizar GiST com ordenação KNN apropriada ou limiar com índice suportado; não alegar que GIN implementa o mesmo caminho KNN. Confirmar plano de consulta.

**Adaptação:** comparar apenas referências de identidade. Regras de padding, tratamento de caracteres não alfanuméricos e tamanho de string precisam seguir a implementação escolhida, com conferência da normalização comum. Número parecido não é identidade equivalente.

**Dependências:** PostgreSQL com `CREATE EXTENSION pg_trgm`, cliente `psycopg`. Sem modelo, treino neural, GPU ou API.

**Parâmetros propostos:** limiar em {0,3; 0,5; 0,7; 0,9}, top-k em {10; 20; 100}; tipo de índice GiST como perfil principal, GIN em ablação identificada. Esses valores são grade de dev, não garantia de qualidade. Registrar tamanho do índice e normalização.

**Critério específico:** qualidade em variações reais de grafia, falsos positivos entre identificadores vizinhos e comportamento de referências muito curtas. O corpus completo continua igual ao dos demais métodos.

## 6. Ficha C1-M4 — distância de edição

**Fundamento:** Wagner e Fischer, *The String-to-String Correction Problem*, 1974. [Artigo/DOI](https://doi.org/10.1145/321796.321811). O problema de distância de edição é estabelecido; a biblioteca moderna pode usar algoritmos otimizados em vez de executar literalmente a programação dinâmica original.

**Implementação pública:** [rapidfuzz/RapidFuzz](https://github.com/rapidfuzz/RapidFuzz). Usar especificamente [`rapidfuzz.distance.Levenshtein`](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html), não uma função genérica `fuzz.ratio` apresentada como equivalente.

**Arquitetura:** referência canônica → comparação com referências candidatas → distância de inserção/remoção/substituição → ranking crescente da distância. Normalizar como score apenas por fórmula publicada/documentada e registrar a fórmula. Distância Levenshtein não trata transposição como uma única operação; Damerau-Levenshtein seria uma ablação distinta.

**Perfis de comparação:** no corpus que couber, varredura completa é o controle de qualidade. Para usar blocking, declarar campos/regras, medir o recall da geração de candidatos e o tempo dessa etapa. Não apresentar o tempo de comparação de uma lista pronta como tempo ponta a ponta. Não comparar varredura e método bloqueado como se tivessem o mesmo conjunto candidato.

**Dependências:** Python e RapidFuzz (extensão otimizada e requisitos de runtime conforme distribuição fixada). Sem modelo, GPU ou chave. Não substituir silenciosamente por outra biblioteca se a wheel não for compatível.

**Parâmetros propostos:** pesos (1,1,1); distância máxima {0; 1; 2}; top-k {10; 20; 100}; sem limite como referência em amostra de desenvolvimento quando viável. Os erros devem vir das consultas reais existentes; não gerar typos artificiais nesta etapa.

**Critério específico:** quantas variações reais recupera e quantas identidades erradas aceita. Campo explicitamente contraditório e diferença de um dígito precisam ser auditados: um caractere pode mudar totalmente o alvo jurídico.

## 7. Ficha C1-M5 — vinculação probabilística

**Fundamento:** Fellegi e Sunter, *A Theory for Record Linkage*, 1969. [Artigo/DOI](https://doi.org/10.1080/01621459.1969.10501049). O problema é reconhecer registros que representam o mesmo objeto a partir de evidências de campos.

**Implementação pública:** [moj-analytical-services/splink](https://github.com/moj-analytical-services/splink). [Artigo do Splink, 2022](https://doi.org/10.23889/ijpds.v7i3.1794). A origem no Ministério da Justiça britânico não é evidência de desempenho em jurisprudência brasileira.

**Arquitetura:** consulta convertida em registro parcial → geração de pares candidatos (`link_only`) → níveis de concordância de campos → pesos probabilísticos → decisão de vínculo, não vínculo ou revisão. Não é um modelo BERT, nem embeddings de documentos.

**Adaptação:** identificar campos independentes/informativos disponíveis no acervo e distinguir ausência de divergência. Não usar número e sua repetição dentro da referência canônica como evidências independentes sem reconhecer dependência. Configurar comparações e blocking antes do teste. Não executar deduplicação/clustering transitivo para resolver uma consulta individual e chamar isso de busca C1.

**Estimação:** aprender parâmetros de concordância/não concordância com dados de treino permitidos; opções de estimação devem seguir a versão fixada do Splink. Se não houver informação suficiente para estimar parâmetros confiáveis, registrar inviabilidade e não inventar probabilidades ou atribuir pesos manuais como se fossem aprendizado publicado. Probabilidade estimada não é automaticamente calibrada.

**Dependências da fonte inspecionada:** Splink, DuckDB, PyArrow e SQLGlot; Python >=3.10 conforme pyproject consultado. README e pyproject podem divergir, por isso a versão de execução e seu resolvedor precisam ser congelados. Spark e backend distribuído não são requisitos para o perfil local.

**Chaves/modelos:** nenhum endpoint de embeddings e nenhuma chave. Há ajuste estatístico local. Tempo de estimação, labels usados e custo do blocking entram no relatório.

**Parâmetros:** regras de blocking; níveis de comparação por campo; tratamento de nulos; estimação de m/u/prior; dois limiares de decisão ajustados em dev; orçamento de candidatos. Não publicar grade numérica de probabilidade antes de verificar calibração e dados.

**Critério específico:** precisão dos vínculos automáticos, cobertura, revisão/abstenção e falso vínculo entre identidades distintas. Brier score ou calibração só serão avaliados em pares rotulados elegíveis e separados do treino.

## 8. Fontes inspecionadas versus ambiente de execução

Revisões GitHub conferidas em 29/10/2026:

| Implementação | Commit upstream inspecionado |
|---|---|
| PostgreSQL (M1/M3) | `27c844034f827b3910bc8a358780c6609ba87a41` |
| Pyserini (M2) | `b492f8b82c3a626a02227834ff6ea5d7a5daface` |
| RapidFuzz (M4) | `09328422916b13181238660cd3b23a71905d1ec9` |
| Splink (M5) | `5b719296d62bc48d55c1a63322fd60c0bfba4c2e` |

Esses hashes registram código consultado. Não são uma combinação de versões já instalada/testada. O lock de execução, imagem/binário, build e dependências transitivas permanecem pendentes. Não instalar versões de desenvolvimento por obrigação de igualar o HEAD; pode-se selecionar release estável, registrando o desvio e conferindo a API.

## 9. Dados: usar o repositório indicado sem substituir o acervo

O usuário indicou `https://github.com/lops-legal/lopsir-benchmark` como fonte do acervo. Na inspeção da main `3e00c1d52625158b45ea1ab2eafc92bce892b84b`, havia documentação, scripts e fixtures históricas em `examples/`, mas nenhum arquivo de corpus de jurisprudência; a lista de releases não expôs assets de dados. A branch c1 acrescenta especificações, não documentos jurídicos.

Isso não significa que o acervo de 370 mil jurisprudências não exista. Significa que sua localização física/conexão ainda não está identificada nos artefatos inspecionados. O repositório é a fonte de trabalho; nenhum corpus externo foi adicionado. `source_repository` fica preenchido e `corpus_path`/`connection_ref` ficam nulos até o vínculo real.

**Bloqueio de execução:** não substituir o acervo pelas quatro consultas `demo-*`; não fabricar metadados; não baixar outro dataset; não estimar qualidade sobre decisões que não foram lidas. Continuar a especificação e os adaptadores que não dependem dos dados, mas não abrir o teste.

### Contrato de dados lógico

```text
identities: entity_id, object_type, reference_original, identity_fields,
            source_record_ids, version_policy, source_locator
queries: query_id, text_original, intent=C1, origin, split, identity_group_id,
         provided_fields, known_status
qrels: query_id, entity_id, relevance, provenance, review_status
decisions: query_id, action, accepted_entity_ids, candidate_entity_ids,
           ambiguity_flag, score_type, score, reason
```

`known_status` é `unique`, `ambiguous`, `absent_from_snapshot` ou `unresolved`. Não inferir inexistência no mundo jurídico a partir de ausência no snapshot. `unresolved` fica fora das métricas de identidade até revisão, com contagem explícita. Não preencher esses campos a partir do método que acertou: a verdade deve ser independente do ranking.

Entidade e registro físico são distintos. Vários excertos de um acórdão devem ser agrupados ou avaliados no nível declarado. Duplicatas do mesmo alvo não podem multiplicar o denominador nem os acertos.

## 10. Pipeline comum aos cinco métodos

1. **Inventariar:** ler o acervo real e produzir schema, contagens de registros/entidades, ausências e duplicatas.
2. **Fixar a tarefa:** definir se cada consulta procura documento, acórdão ou processo. Separar citação de identidade.
3. **Validar consultas reais:** localizar as já existentes e seus julgamentos. Qualquer construção de consultas a partir de metadados exige autorização específica e rótulo próprio; não será chamada de log real.
4. **Separar treino/dev/test:** usar splits existentes se válidos; caso contrário, propor split agrupado por identidade e congelá-lo antes do ajuste. Não usar a mesma identidade em lados diferentes por causa de variantes.
5. **Congelar preparação:** parser, aliases, serialização e política de versões compartilhados. Medir erros de extração antes do scoring.
6. **Executar os cinco métodos:** mesmo corpus e consultas; configurações salvas; tempo total e por etapa; falhas e abstenções preservadas.
7. **Ajustar em dev:** orçamento de tentativas comparável, sem olhar o teste. Salvar também tentativas mal-sucedidas.
8. **Abrir teste:** configurações fixas, ordem de execução alternada, recursos e concorrência registrados.
9. **Revisar erros:** identidade incorreta, ambiguidade ignorada, alvo ausente aceito, campo extraído errado ou versão equivocada.
10. **Publicar:** relatório por método, comparação por condição e conclusão. C2 só começa sua execução depois da revisão desse resultado.

Ter cinco métodos na especificação não obriga a fabricar cinco resultados: um que não puder ser executado terá relatório de inviabilidade com motivo, sem score zero substituindo uma medição inexistente.

## 11. Avaliação por condição

### Referências inequívocas

- Hit@1, MRR@10, Recall@20/100, nDCG@10 e Precision@10/20 sobre os positivos conhecidos.
- Precisão de identidade automática = consultas únicas corretamente resolvidas / consultas com decisão automática única.
- Cobertura automática = consultas elegíveis com decisão automática / consultas elegíveis.
- Separar ranking puro da decisão com limiar. Um método que se abstém sempre não será chamado de preciso sem mostrar cobertura.

Com só um alvo, Precision@20 tem teto 1/20 e pouca utilidade decisória; será contextualizada, não usada para preferir um sistema que devolve itens desnecessários. Não completar rankings com documentos errados para chegar a vinte.

### Referências ambíguas

- Igualdade exata do conjunto devolvido versus conjunto elegível quando houver anotação exaustiva.
- Precision/Recall do conjunto e taxa de declaração de ambiguidade.
- Nenhum candidato aleatoriamente escolhido será contabilizado como identificação inequívoca correta.

### Alvos ausentes do snapshot

- Taxa de aceitação indevida: consultas ausentes para as quais o método declara uma identidade / consultas ausentes avaliáveis.
- Taxa de rejeição correta e política de abstenção.
- MRR/Recall/nDCG de relevância não são definidos como se houvesse um positivo. Relatar `null` e contagens separadas.

### Recursos e rapidez

Medir parsing, blocking/recuperação, scoring, decisão e total. Registrar p50/p95/p99, concorrência, QPS, erros/timeout, pico de RAM, bytes de índice, construção, carregamento, atualização e tempo até pesquisável. Não zerar falhas nem removê-las da população. Repetições, cache e threads constam do manifesto.

Preferir bootstrap pareado por grupo de identidade, com intervalo de 95%. Amostras pequenas ou ausência de classes ambígua/ausente devem limitar a conclusão. Não criar esses casos artificialmente para preencher a tabela.

## 12. Hipóteses C1 e critério de escolha

| Hipótese | Comparação | O que pode refutá-la |
|---|---|---|
| C1-H1 | M1 tem melhor custo para referência íntegra com alta qualidade | Parser/normalização gera colisões ou outros métodos têm melhor fronteira |
| C1-H2 | M2 ajuda expressão textual menos regular | Não melhora cobertura ou aumenta aceitação errada |
| C1-H3 | M3 recupera variações reais sem comparar todas as strings | Ganho pequeno ou falsos vínculos/índice caro demais |
| C1-H4 | M4 oferece correção controlável para erros reais | Custo excessivo ou confusão entre números válidos próximos |
| C1-H5 | M5 combina melhor evidências incompletas | Falta de dados/estimação ou ausência de ganho após custo e calibração |

Não escolher uma arquitetura antes de medir. Uma arquitetura composta exato+fallback poderá ser estudada depois como ablação de composição, com custo de todas as etapas; não será uma sexta metodologia apresentada como invenção SOTA.

## 13. Saídas e estado

Cada método deverá gerar `manifest.json`, `run.tsv`, `decisions.jsonl`, `timings.jsonl`, `resources.json`, `metrics.json` e `report.md`. Arquivos reais de corpus/credenciais ficam fora do Git; registrar hashes e instruções de acesso permitidas. Não publicar conteúdo jurídico sensível por automatismo.

Estado atual: fontes e especificação conferidas; sem corpus conectado, sem adaptadores executados e sem resultados jurídicos. O registro legível por máquina está em [c1.methods.json](../../configs/c1.methods.json). O relatório de prontidão deve listar bloqueios, nunca inventar métricas.
