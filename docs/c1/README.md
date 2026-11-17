# C1 — localização de referências e identidades

Estado: etapa ativa de especificação. Execução sobre as 370 mil jurisprudências reais aguarda a localização e o esquema do acervo. Não usar a fixture `demo-*` como base científica e não criar novas referências fictícias.

## Intenção

Encontrar um objeto identificado na consulta: um documento, um acórdão, um processo ou um conjunto de identidades legitimamente compatíveis. Uma pergunta sobre aplicação de uma tese é C3; uma pesquisa temática é C2. Documentos que apenas citam o identificador não são automaticamente o alvo de C1.

A primeira decisão de dados é a unidade: processo pode conter vários acórdãos; um acórdão pode aparecer em vários excertos; um documento pode ter versões. O número isolado pode não ser único entre anos ou instituições. Essas relações precisam ser verificadas nos dados reais.

## Cinco metodologias selecionadas para detalhamento

| ID | Metodologia publicada | Hipótese de vantagem a testar |
|---|---|---|
| C1-M1 | Busca exata por chave composta com índice B-tree | Baixo custo e alta precisão para referência íntegra |
| C1-M2 | Recuperação lexical BM25 | Robustez à expressão textual e à presença de termos adicionais |
| C1-M3 | Similaridade por q-grams/trigramas indexados | Recuperação com variações locais de escrita |
| C1-M4 | Distância de edição Levenshtein | Tolerância controlada a erros de digitação |
| C1-M5 | Vinculação probabilística Fellegi–Sunter | Combinação explicável de campos incompletos ou divergentes |

São métodos existentes; a adequação e os limiares para referências jurídicas são adaptações experimentais. Não são declarados cinco métodos SOTA de recuperação semântica: C1 tem uma tarefa de identidade distinta de C2/C3. Cada um precisa da mesma avaliação e de um relatório, inclusive se falhar.

Fontes primárias e implementações: B-tree ([artigo](https://doi.org/10.1007/BF00288683), [PostgreSQL](https://github.com/postgres/postgres)); BM25 ([Pyserini](https://arxiv.org/abs/2102.10073), [código](https://github.com/castorini/pyserini)); q-grams ([Ukkonen](https://doi.org/10.1016/0304-3975(92)90143-4), [pg_trgm](https://github.com/postgres/postgres/tree/master/contrib/pg_trgm)); distância de edição ([Wagner–Fischer](https://doi.org/10.1145/321796.321811), [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)); vinculação ([Fellegi–Sunter](https://doi.org/10.1080/01621459.1969.10501049), [Splink](https://github.com/moj-analytical-services/splink)).

## Critérios

Hit@1 e MRR@10; precisão de identidade; recuperação do conjunto correto para referências ambíguas; rejeição de inexistentes; qualidade dos candidatos; cobertura e taxa de abstenção. Métricas @10/@20 do protocolo comum entram quando definidas. Não exigir que uma busca exata devolva vinte itens apenas para preencher um corte.

Todos os métodos devem fornecer latência por estágio e ponta a ponta, memória, bytes, construção, atualização, falhas e custo. Nenhum requer embedding, GPU ou chave de API.

## Próxima entrada necessária

Conectar o caminho/banco real indicado pelo usuário, mapear os campos de identidade e localizar as consultas/qrels existentes. Derivações de metadados só serão feitas com autorização específica, preservando sua origem. Não tratar consultas derivadas como logs reais de busca.

Consultar o [pipeline comum](../PIPELINE.md) e as [cinco fichas detalhadas de C1](METODOLOGIAS.md), com dependências, fontes, parâmetros, contratos de dados e avaliação por condição. O [registro de métodos](../../configs/c1.methods.json) distingue fontes conferidas de implementações ainda pendentes.

## Conferir prontidão

Na raiz do repositório:

```powershell
python scripts/c1_preflight.py --config configs/c1.methods.json --output reports/c1/readiness.json
```

O comando não baixa dados nem executa métodos. O código de saída **2** significa que faltam entradas/adaptadores/versões; o relatório enumera os bloqueios e mantém métricas de pesquisa nulas. O código **1** significa configuração inválida. O código **0** significa apenas que as verificações de configuração passaram, não que a pesquisa foi executada.
