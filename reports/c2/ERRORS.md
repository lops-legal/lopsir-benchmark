# C2 — análise de erros (teste, gerado)

nDCG@10 por consulta de teste. Textos das consultas vêm do JurisTCU (palavras-chave curtas); nenhum trecho de documento é reproduzido.

## Lexical (M1 BM25) × denso (M5r Nemotron denso (ref.))

Critério: ambos falham se os dois < 0.1; ambos acertam se os dois ≥ 0.5; vence quem supera o outro por ≥ 0,1.

| Situação | Consultas | % | Ids |
|---|---|---|---|
| BM25 vence | 14 | 20% | 10, 14, 17, 25, 28, 37, 44, 47, 52, 53, 54, 83, 84, 91 |
| denso vence | 23 | 33% | 3, 6, 7, 15, 19, 26, 31, 34, 39, 40, 42, 46, 48, 49, 60, 65, 74, 79, 80, 85, 88, 93, 99 |
| ambos falham | 3 | 4% | 5, 8, 23 |
| ambos acertam | 15 | 21% | 43, 51, 55, 56, 66, 67, 69, 73, 75, 76, 81, 87, 92, 94, 95 |
| parecidos | 15 | 21% | 1, 4, 9, 11, 16, 21, 22, 35, 41, 59, 62, 82, 96, 97, 98 |

**BM25 vence:** `diarias e passagens` (real; curta, conjunção, sem acento); `decreto-lei 4.657/1942` (real; média, referência); `impedimento de licitar e contratar` (real; média, conjunção); `exigência de atestado de capacidade` (real; média); `mera participação e epp` (real; média, conjunção); `planejamento estratégico` (real; curta); `interesse recíproco` (real; curta); `publicidade e propaganda` (real; curta, conjunção); `citação válida falecimento` (sintética; média); `garantia contratual patrimônio líquido mínimo` (sintética; média); `garantia de participação patrimônio líquido mínimo` (sintética; média); `irregulares despesas desnecessárias e anteriores à celebração do contrato` (sintética; longa, conjunção); `vínculo trabalhista ou societário pré-existente competitividade das licitantes` (sintética; longa); `controle adesão` (sintética; curta)

**denso vence:** `aditivo a contrato` (real; curta); `restrição a competitividade` (real; curta); `acréscimos e supressões` (real; curta, conjunção); `contas e materialidade` (real; curta, conjunção); `fraude a licitacao` (real; curta, sem acento); `contrato com a administração pública` (real; média); `medida cautelar` (real; curta); `publicidade e concurso público` (real; média, conjunção); `citação e validade` (real; curta, conjunção); `multa a particulares` (real; curta); `edital modificação` (real; curta); `planilha de custos e formação de preços` (real; média, conjunção); `processo seletivo e sistema s` (real; média, conjunção); `modalidade de licitação` (real; curta); `responsabilidade do gestor sucessor omissão do antecessor` (sintética; média); `pesquisa de preços obrigatória em licitações` (sintética; média); `prorrogação de contrato administrativo término prazo de vigência` (sintética; longa); `instrutor treinamento inexigibilidade de licitação` (sintética; média); `reajuste de preços e repactuação` (sintética; média, conjunção); `técnica e preço profissionais quadro permanente` (sintética; média, conjunção); `exigência comprovação de quantitativos mínimos características semelhantes` (sintética; longa); `acumulação de cargo secretário municipal professor` (sintética; média); `contratações de software cartas de exclusividade` (sintética; média)

**ambos falham:** `sobrepreço e superfaturamento` (real; curta, conjunção); `obras e serviços de engenharia` (real; média, conjunção); `inidoneidade de licitante` (real; curta)

## M2 Query2doc contra o BM25

| | Consulta | Tipo | BM25 | Método | Δ |
|---|---|---|---|---|---|
| ganho | `falecimento e multa` | real; curta, conjunção | 0.07 | 0.27 | +0.20 |
| ganho | `medida cautelar` | real; curta | 0.00 | 0.17 | +0.17 |
| ganho | `planilha de custos e formação de preços` | real; média, conjunção | 0.15 | 0.30 | +0.16 |
| ganho | `sobrepreço e superfaturamento` | real; curta, conjunção | 0.00 | 0.11 | +0.11 |
| ganho | `marca aquisição cartuchos` | sintética; média | 0.66 | 0.76 | +0.10 |
| perda | `técnica e preço` | real; curta, conjunção | 0.40 | 0.00 | -0.40 |
| perda | `mera participação e epp` | real; média, conjunção | 0.67 | 0.38 | -0.29 |
| perda | `despesas sem cobertura contratual multa` | sintética; média | 0.51 | 0.28 | -0.23 |
| perda | `prorrogação de contrato administrativo término prazo de vigência` | sintética; longa | 0.46 | 0.25 | -0.21 |
| perda | `planejamento estratégico` | real; curta | 0.54 | 0.35 | -0.19 |

## M3 SPLADE-PT-BR contra o BM25

| | Consulta | Tipo | BM25 | Método | Δ |
|---|---|---|---|---|---|
| ganho | `inexequibilidade e comprovação` | real; curta, conjunção | 0.18 | 0.46 | +0.28 |
| ganho | `sobrepreço e superfaturamento` | real; curta, conjunção | 0.00 | 0.28 | +0.28 |
| ganho | `fracionamento de despesas` | real; curta | 0.07 | 0.35 | +0.28 |
| ganho | `restrição a competitividade` | real; curta | 0.08 | 0.36 | +0.28 |
| ganho | `padronização marca` | real; curta | 0.59 | 0.79 | +0.20 |
| perda | `irregulares despesas desnecessárias e anteriores à celebração do contrato` | sintética; longa, conjunção | 0.62 | 0.04 | -0.58 |
| perda | `vedação à inclusão documento habilitação diligência` | sintética; média | 0.51 | 0.00 | -0.51 |
| perda | `garantia contratual patrimônio líquido mínimo` | sintética; média | 0.64 | 0.16 | -0.48 |
| perda | `diarias e passagens` | real; curta, conjunção, sem acento | 0.46 | 0.00 | -0.46 |
| perda | `prescrição da pretensão punitiva julgamento das contas` | sintética; média | 0.56 | 0.10 | -0.46 |

## M5 Híbrido contra o BM25

| | Consulta | Tipo | BM25 | Método | Δ |
|---|---|---|---|---|---|
| ganho | `contrato com a administração pública` | real; média | 0.10 | 0.25 | +0.15 |
| ganho | `restrição a competitividade` | real; curta | 0.08 | 0.22 | +0.14 |
| ganho | `prorrogação de contrato administrativo término prazo de vigência` | sintética; longa | 0.46 | 0.57 | +0.11 |
| ganho | `licitação e preço de mercado` | real; média, conjunção | 0.11 | 0.22 | +0.11 |
| ganho | `exigência comprovação de quantitativos mínimos características semelhantes` | sintética; longa | 0.32 | 0.43 | +0.11 |
| perda | `diarias e passagens` | real; curta, conjunção, sem acento | 0.46 | 0.29 | -0.17 |
| perda | `citação válida falecimento` | sintética; média | 0.59 | 0.51 | -0.07 |
| perda | `decreto-lei 4.657/1942` | real; média, referência | 0.22 | 0.16 | -0.06 |
| perda | `exigência de atestado de capacidade` | real; média | 0.14 | 0.08 | -0.06 |
| perda | `bens e serviços comuns` | real; média, conjunção | 0.13 | 0.08 | -0.05 |

## M2a RM3 (ablação) contra o BM25

| | Consulta | Tipo | BM25 | Método | Δ |
|---|---|---|---|---|---|
| ganho | `inexequibilidade e comprovação` | real; curta, conjunção | 0.18 | 0.34 | +0.16 |
| ganho | `contrato com a administração pública` | real; média | 0.10 | 0.25 | +0.15 |
| ganho | `contas e materialidade` | real; curta, conjunção | 0.00 | 0.14 | +0.14 |
| ganho | `técnica e preço` | real; curta, conjunção | 0.40 | 0.53 | +0.13 |
| ganho | `renovação de contrato serviços de natureza continuada pesquisa de preços` | sintética; longa | 0.50 | 0.58 | +0.08 |
| perda | `garantia contratual patrimônio líquido mínimo` | sintética; média | 0.64 | 0.43 | -0.21 |
| perda | `concessão remunerada de uso de bens públicos modalidade` | sintética; longa | 0.60 | 0.52 | -0.08 |
| perda | `fiscalizacao de contratos` | real; curta, sem acento | 0.23 | 0.15 | -0.08 |
| perda | `exigência de atestado de capacidade` | real; média | 0.14 | 0.06 | -0.08 |
| perda | `técnica e preço profissionais quadro permanente` | sintética; média, conjunção | 0.23 | 0.16 | -0.07 |

## M5r Nemotron denso (ref.) contra o BM25

| | Consulta | Tipo | BM25 | Método | Δ |
|---|---|---|---|---|---|
| ganho | `multa a particulares` | real; curta | 0.00 | 0.45 | +0.45 |
| ganho | `edital modificação` | real; curta | 0.10 | 0.53 | +0.43 |
| ganho | `responsabilidade do gestor sucessor omissão do antecessor` | sintética; média | 0.18 | 0.46 | +0.28 |
| ganho | `processo seletivo e sistema s` | real; média, conjunção | 0.21 | 0.48 | +0.27 |
| ganho | `acréscimos e supressões` | real; curta, conjunção | 0.08 | 0.33 | +0.25 |
| perda | `irregulares despesas desnecessárias e anteriores à celebração do contrato` | sintética; longa, conjunção | 0.62 | 0.20 | -0.42 |
| perda | `mera participação e epp` | real; média, conjunção | 0.67 | 0.34 | -0.33 |
| perda | `interesse recíproco` | real; curta | 0.68 | 0.35 | -0.33 |
| perda | `vínculo trabalhista ou societário pré-existente competitividade das licitantes` | sintética; longa | 0.58 | 0.31 | -0.27 |
| perda | `publicidade e propaganda` | real; curta, conjunção | 0.48 | 0.23 | -0.26 |

## Tabela completa (nDCG@10)

| Id | Consulta | Tipo | M1 | M2 | M3 | M5 | M2a | M5r | Melhor |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `técnica e preço` | real; curta, conjunção | 0.40 | 0.00 | 0.11 | 0.42 | **0.53** | 0.39 | M2a |
| 3 | `aditivo a contrato` | real; curta | 0.00 | 0.00 | 0.00 | 0.08 | 0.00 | **0.15** | M5r |
| 4 | `adesão a ata de registro de preços` | real; média | 0.25 | 0.11 | 0.11 | 0.27 | 0.32 | **0.32** | M5r |
| 5 | `sobrepreço e superfaturamento` | real; curta, conjunção | 0.00 | 0.11 | **0.28** | 0.00 | 0.00 | 0.00 | M3 |
| 6 | `restrição a competitividade` | real; curta | 0.08 | 0.00 | **0.36** | 0.22 | 0.09 | 0.20 | M3 |
| 7 | `acréscimos e supressões` | real; curta, conjunção | 0.08 | 0.14 | 0.15 | 0.11 | 0.08 | **0.33** | M5r |
| 8 | `obras e serviços de engenharia` | real; média, conjunção | **0.05** | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | M1 |
| 9 | `fiscalizacao de contratos` | real; curta, sem acento | 0.23 | 0.08 | 0.00 | 0.28 | 0.15 | **0.31** | M5r |
| 10 | `diarias e passagens` | real; curta, conjunção, sem acento | 0.46 | 0.31 | 0.00 | 0.29 | **0.52** | 0.22 | M2a |
| 11 | `bens e serviços comuns` | real; média, conjunção | 0.13 | 0.00 | 0.00 | 0.08 | **0.19** | 0.14 | M2a |
| 14 | `decreto-lei 4.657/1942` | real; média, referência | 0.22 | **0.29** | 0.24 | 0.16 | 0.16 | 0.00 | M2 |
| 15 | `contas e materialidade` | real; curta, conjunção | 0.00 | 0.00 | 0.00 | 0.10 | 0.14 | **0.22** | M5r |
| 16 | `inexequibilidade e comprovação` | real; curta, conjunção | 0.18 | 0.18 | **0.46** | 0.26 | 0.34 | 0.23 | M3 |
| 17 | `impedimento de licitar e contratar` | real; média, conjunção | 0.22 | 0.12 | 0.00 | 0.21 | **0.23** | 0.06 | M2a |
| 19 | `fraude a licitacao` | real; curta, sem acento | 0.00 | 0.06 | 0.00 | 0.00 | 0.00 | **0.19** | M5r |
| 21 | `fracionamento de despesas` | real; curta | 0.07 | 0.14 | **0.35** | 0.07 | 0.00 | 0.14 | M3 |
| 22 | `novo e improrrogável prazo` | real; média, conjunção | **0.22** | 0.08 | 0.00 | **0.22** | 0.21 | 0.16 | M1/M5 |
| 23 | `inidoneidade de licitante` | real; curta | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | nenhum |
| 25 | `exigência de atestado de capacidade` | real; média | **0.14** | 0.00 | 0.07 | 0.08 | 0.06 | 0.00 | M1 |
| 26 | `contrato com a administração pública` | real; média | 0.10 | 0.00 | 0.08 | 0.25 | 0.25 | **0.34** | M5r |
| 28 | `mera participação e epp` | real; média, conjunção | **0.67** | 0.38 | 0.32 | 0.65 | 0.66 | 0.34 | M1 |
| 31 | `medida cautelar` | real; curta | 0.00 | **0.17** | 0.15 | 0.00 | 0.00 | 0.14 | M2 |
| 34 | `publicidade e concurso público` | real; média, conjunção | 0.14 | 0.00 | 0.00 | 0.18 | 0.14 | **0.33** | M5r |
| 35 | `falecimento e multa` | real; curta, conjunção | 0.07 | **0.27** | 0.25 | 0.07 | 0.14 | 0.11 | M2 |
| 37 | `planejamento estratégico` | real; curta | **0.54** | 0.35 | 0.48 | 0.52 | 0.53 | 0.39 | M1 |
| 39 | `citação e validade` | real; curta, conjunção | 0.27 | 0.30 | 0.38 | 0.37 | 0.29 | **0.50** | M5r |
| 40 | `multa a particulares` | real; curta | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **0.45** | M5r |
| 41 | `licitação e preço de mercado` | real; média, conjunção | 0.11 | 0.00 | 0.00 | **0.22** | 0.11 | 0.21 | M5 |
| 42 | `edital modificação` | real; curta | 0.10 | 0.19 | 0.30 | 0.13 | 0.17 | **0.53** | M5r |
| 43 | `padronização marca` | real; curta | 0.59 | 0.61 | 0.79 | 0.59 | 0.59 | **0.82** | M5r |
| 44 | `interesse recíproco` | real; curta | 0.68 | 0.62 | 0.37 | **0.74** | 0.68 | 0.35 | M5 |
| 46 | `planilha de custos e formação de preços` | real; média, conjunção | 0.15 | **0.30** | 0.15 | 0.23 | 0.15 | 0.26 | M2 |
| 47 | `publicidade e propaganda` | real; curta, conjunção | 0.48 | 0.39 | 0.27 | 0.46 | **0.52** | 0.23 | M2a |
| 48 | `processo seletivo e sistema s` | real; média, conjunção | 0.21 | 0.26 | 0.34 | 0.20 | 0.20 | **0.48** | M5r |
| 49 | `modalidade de licitação` | real; curta | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **0.13** | M5r |
| 51 | `concessão remunerada de uso de bens públicos modalidade` | sintética; longa | 0.60 | 0.65 | **0.73** | 0.68 | 0.52 | 0.66 | M3 |
| 52 | `citação válida falecimento` | sintética; média | **0.59** | 0.47 | 0.52 | 0.51 | 0.58 | 0.39 | M1 |
| 53 | `garantia contratual patrimônio líquido mínimo` | sintética; média | 0.64 | 0.55 | 0.16 | **0.65** | 0.43 | 0.41 | M5 |
| 54 | `garantia de participação patrimônio líquido mínimo` | sintética; média | 0.58 | **0.67** | 0.35 | 0.58 | 0.52 | 0.40 | M2 |
| 55 | `despesas sem cobertura contratual multa` | sintética; média | 0.51 | 0.28 | 0.22 | **0.58** | 0.55 | 0.53 | M5 |
| 56 | `uso de áreas comerciais em aeroportos pregão` | sintética; média | 0.54 | 0.41 | 0.39 | 0.57 | 0.61 | **0.64** | M5r |
| 59 | `extrapolação dos limites para alterações consensuais qualitativas de contratos de obras e serviços` | sintética; longa, conjunção | 0.38 | 0.41 | **0.51** | 0.39 | 0.38 | 0.46 | M3 |
| 60 | `responsabilidade do gestor sucessor omissão do antecessor` | sintética; média | 0.18 | 0.16 | 0.00 | 0.24 | 0.14 | **0.46** | M5r |
| 62 | `objeto do certame contrato social licitante` | sintética; média | 0.45 | 0.45 | 0.15 | 0.46 | 0.45 | **0.48** | M5r |
| 65 | `pesquisa de preços obrigatória em licitações` | sintética; média | 0.26 | 0.33 | 0.11 | 0.25 | 0.25 | **0.41** | M5r |
| 66 | `vantajosidade adesão à ata` | sintética; média | 0.62 | 0.64 | 0.39 | **0.72** | 0.59 | 0.63 | M5 |
| 67 | `compensação entre acréscimos e supressões contratos administrativos` | sintética; média, conjunção | 0.61 | **0.70** | 0.17 | 0.66 | 0.67 | 0.66 | M2 |
| 69 | `marca aquisição cartuchos` | sintética; média | 0.66 | 0.76 | 0.51 | 0.66 | 0.65 | **0.82** | M5r |
| 73 | `pontuação desarrazoada licitações técnica e preço` | sintética; média, conjunção | 0.54 | 0.57 | 0.43 | 0.63 | 0.56 | **0.65** | M5r |
| 74 | `prorrogação de contrato administrativo término prazo de vigência` | sintética; longa | 0.46 | 0.25 | 0.17 | 0.57 | 0.44 | **0.60** | M5r |
| 75 | `atestado de capacidade técnica serviços advocatícios conselho de fiscalização profissional` | sintética; longa | 0.58 | 0.56 | 0.33 | **0.61** | 0.53 | 0.55 | M5 |
| 76 | `reposição de importâncias indevidamente percebidas boa-fé servidores erro escusável por órgão/entidade` | sintética; longa | 0.55 | 0.59 | 0.26 | 0.53 | **0.60** | 0.53 | M2a |
| 79 | `instrutor treinamento inexigibilidade de licitação` | sintética; média | 0.30 | 0.30 | 0.20 | 0.36 | 0.30 | **0.55** | M5r |
| 80 | `reajuste de preços e repactuação` | sintética; média, conjunção | 0.46 | 0.45 | 0.42 | 0.47 | 0.46 | **0.58** | M5r |
| 81 | `recomposição reajuste` | sintética; curta | 0.61 | 0.49 | 0.56 | 0.61 | 0.61 | **0.64** | M5r |
| 82 | `retenção de pagamentos perda da regularidade fiscal` | sintética; média | 0.47 | 0.37 | 0.31 | 0.47 | 0.53 | **0.54** | M5r |
| 83 | `irregulares despesas desnecessárias e anteriores à celebração do contrato` | sintética; longa, conjunção | 0.62 | **0.67** | 0.04 | 0.63 | 0.64 | 0.20 | M2 |
| 84 | `vínculo trabalhista ou societário pré-existente competitividade das licitantes` | sintética; longa | **0.58** | 0.56 | 0.20 | **0.58** | **0.58** | 0.31 | M1/M5/M2a |
| 85 | `técnica e preço profissionais quadro permanente` | sintética; média, conjunção | 0.23 | 0.17 | 0.00 | 0.22 | 0.16 | **0.34** | M5r |
| 87 | `vedação à inclusão documento habilitação diligência` | sintética; média | **0.51** | 0.45 | 0.00 | **0.51** | 0.45 | 0.50 | M1/M5 |
| 88 | `exigência comprovação de quantitativos mínimos características semelhantes` | sintética; longa | 0.32 | 0.27 | 0.39 | 0.43 | 0.40 | **0.53** | M5r |
| 91 | `controle adesão` | sintética; curta | 0.14 | 0.00 | 0.00 | 0.14 | **0.15** | 0.00 | M2a |
| 92 | `alvará de funcionamento habilitação jurídica` | sintética; média | 0.68 | 0.61 | 0.31 | 0.68 | 0.68 | **0.80** | M5r |
| 93 | `acumulação de cargo secretário municipal professor` | sintética; média | 0.36 | 0.37 | 0.29 | 0.36 | 0.33 | **0.55** | M5r |
| 94 | `prescrição da pretensão punitiva julgamento das contas` | sintética; média | 0.56 | 0.53 | 0.10 | **0.63** | 0.56 | 0.63 | M5 |
| 95 | `Banco de Preços em Saúde referência medicamentos` | sintética; média | 0.79 | 0.73 | 0.74 | 0.82 | 0.79 | **0.92** | M5r |
| 96 | `alteração contratual serviços já previstos no edital` | sintética; média | 0.34 | 0.28 | **0.44** | 0.43 | 0.41 | 0.40 | M3 |
| 97 | `licitação princípio da legalidade estrita afastado` | sintética; média | **0.39** | **0.39** | 0.00 | **0.39** | **0.39** | **0.39** | M1/M2/M5/M2a/M5r |
| 98 | `renovação de contrato serviços de natureza continuada pesquisa de preços` | sintética; longa | 0.50 | 0.49 | 0.51 | 0.58 | **0.58** | 0.55 | M2a |
| 99 | `contratações de software cartas de exclusividade` | sintética; média | 0.45 | 0.41 | 0.16 | 0.41 | 0.45 | **0.56** | M5r |
