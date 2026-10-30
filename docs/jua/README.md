# JUÁ — trilha de reprodução independente

Branch: `jua`. Estado: protocolo; arquivos nativos e permissões de obtenção ainda não indicados para execução. Não importar outro conjunto de dados sem instrução do usuário.

## O que esta trilha significa

O benchmark [JUÁ v2](https://arxiv.org/abs/2604.06098v2) será uma referência de metodologia e, quando seus artefatos forem disponibilizados/indicados pelo usuário no projeto, uma trilha de reprodução. Rodar métodos sobre o acervo próprio de 370 mil jurisprudências é outra avaliação e não reproduz os números da Tabela 2 do JUÁ.

JUÁ não é C1/C2/C3: reúne tarefas que se aproximam de C2 e C3. A classificação proposta está no [pipeline comum](../PIPELINE.md). Não transferir seus qrels para consultas ou documentos diferentes.

## Reprodução a preservar

1. Versão do paper e revisão dos artefatos.
2. Corpus, queries, qrels e splits nativos de cada coleção.
3. Campos usados: por exemplo, só EXCERTO no JurisTCU adaptado; ASSUNTO + TEXTONORMA no NormasTCU.
4. Métricas @10 e convenções do avaliador original.
5. Configurações de recuperação direta versus reordenação de top-1000 BM25.
6. Checkpoints e exposição ao treino; seleção em dev separada do teste.
7. Resultados por coleção e média somente sobre mesma cobertura.

O artigo chama algumas configurações de `Rerank`; isso não demonstra que todas usam cross-encoder. Verificar scoring e código antes da implementação. Analisador BM25 e parâmetros ausentes precisam ser marcados como lacuna, não inventados.

## Entregas futuras

Manifesto nativo, conferência do avaliador, reprodução de baselines disponíveis e relatório de diferenças em relação ao artigo. Se algum artefato não estiver disponível no projeto, registrar `blocked_input` e manter a leitura metodológica; nunca substituir por dados próprios e conservar o rótulo de reprodução.
