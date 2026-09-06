# Guia de RAG e avaliação

## Recuperação de informações
Retrieval-Augmented Generation (RAG) combina recuperação de documentos com geração de texto. Primeiro, o sistema divide os documentos em trechos menores chamados chunks. Uma pergunta é comparada com esses trechos, e os mais relevantes são enviados ao modelo de linguagem como contexto. A resposta deve se apoiar no conteúdo recuperado. Se o contexto não contém a informação solicitada, o modelo deve declarar que não há informação suficiente.

## Chunkização
A chunkização divide um documento em unidades de recuperação. Chunks muito pequenos podem perder o contexto necessário para compreender uma ideia. Chunks muito grandes podem misturar temas e incluir informações irrelevantes. A sobreposição repete uma parte do trecho anterior para preservar continuidade nas fronteiras. Cada chunk deve guardar um identificador e o nome do documento de origem, permitindo rastrear a informação recuperada.

## Recuperação lexical
TF-IDF representa textos por pesos associados às palavras. Termos frequentes em um texto, mas menos comuns no conjunto de documentos, recebem maior importância. A similaridade de cosseno compara a direção dos vetores. Os trechos com maior similaridade com a pergunta são selecionados. Essa abordagem funciona sem uma API de embeddings, mas pode falhar quando a pergunta usa sinônimos ou vocabulário diferente do documento.

## Avaliação sem gabarito
Na avaliação sem ground truth, não existem respostas humanas de referência para comparar diretamente. Um modelo de linguagem pode atuar como juiz, analisando a pergunta, os contextos recuperados e a resposta gerada. O juiz deve seguir critérios explícitos e produzir notas acompanhadas de justificativas. O resultado é uma estimativa e pode variar conforme o modelo e o prompt utilizados.

## Métricas
Faithfulness mede se as afirmações da resposta são sustentadas pelos contextos recuperados. Uma resposta pode ser plausível e ainda assim receber uma nota baixa se apresentar informações que não estão nas fontes. Answer Relevancy mede se a resposta atende à pergunta de forma pertinente e direta. Context Utilization mede quanto das informações relevantes disponíveis nos contextos foi efetivamente utilizado na resposta. Trechos irrelevantes à pergunta não devem reduzir essa última nota.

## Dataset sintético
Um dataset sintético contém perguntas geradas automaticamente a partir dos documentos. A geração deve usar o conteúdo real de um chunk e preservar sua origem. Personas podem influenciar o estilo das perguntas: um estudante busca explicações didáticas, enquanto um gestor busca consequências práticas. O chunk usado para gerar a pergunta não deve ser forçado como resultado da recuperação, pois isso mascararia problemas do mecanismo de busca.
