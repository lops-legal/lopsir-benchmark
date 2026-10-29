# Passagem para o Claude — branch c2

## Objetivo

Preparar C2 no nível metodológico do JUÁ: cinco métodos publicados, código público e relatório comparável para pesquisar expressões jurídicas/palavras-chave no acervo real do LopsIR. Ler primeiro [o pipeline](../PIPELINE.md), [o plano C2](README.md) e [as fichas de C1](../c1/METODOLOGIAS.md).

## Base e divisão do trabalho

Esta branch nasce da base `c1` que contém pipeline, fichas C1 e controle de prontidão. Trabalho ativo de C1 permanece em `c1`; C3 tem `c3`; reprodução JUÁ tem `jua`. Não fazer force-push e não reescrever a história de outros colaboradores.

Priorizar `docs/c2/`, `configs/c2.*`, futuros adaptadores C2 e testes específicos. Coordenar mudanças em contratos compartilhados e no avaliador, para evitar pontuações incompatíveis entre branches. Fazer commits pequenos por entrega e publicar a branch ao concluir cada unidade verificável.

## Restrições do usuário

- Usar as aproximadamente 370 mil jurisprudências reais indicadas no projeto.
- Não criar jurisprudências, metadados de identidade, perguntas ou resultados fictícios.
- Não importar outro conjunto de dados. Links de papers/datasets no SDD são referências, não autorização de importação.
- A main inspecionada ainda não expõe um caminho de corpus: consultar `reports/c1/repository-inventory.json`. Não substituir essa lacuna por `examples/demo-*`.
- Não colocar email pessoal ou credencial em documentação.
- C2 pode ter documentação e código preparados; abrir sua execução após revisão de C1.

## Entrega esperada

1. Conferir as cinco famílias propostas em README.md e selecionar checkpoints/implementações compatíveis com português.
2. Para cada método, documentar artigo, GitHub e revisão, dependências reais, modelo, instrução/prompt, API ou execução local, parâmetros e diferença entre reprodução e adaptação.
3. Mapear as consultas reais C2 e os qrels do acervo quando disponíveis. A verdade de C1 não serve como relevância temática C2.
4. Manter o mesmo corpus/queries/splits por concorrente; tuning somente no dev.
5. Medir nDCG/Precision/Recall/MRR, erros jurídicos, latência, RAM/índice, ingestão, atualização e custo completo.
6. Produzir cinco relatórios, incluindo inviabilidade ou resultado inconclusivo quando cabível. Não declarar método executado só porque existe um pacote instalado.

## Segredos e recursos

Não solicitar chave genérica antecipadamente. Se for indispensável, especificar modelo, endpoint, finalidade e teto estimado primeiro. A máquina diagnosticada tem GPU de 4 GB e RAM de aproximadamente 8 GB; conferir disponibilidade atual e executar um perfil por vez.

Esta passagem é documentação para o usuário/Claude. Nenhuma mensagem foi enviada a outro serviço ou agente.
