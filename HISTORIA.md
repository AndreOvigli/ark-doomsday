# A história do ARK em uma página

O ARK teve duas versões. A primeira foi abandonada e a segunda recomeçou do zero, com outro método. O que mudou entre elas é mais útil para quem chega do que o código em si.

## v1: a colcha de remendos (21 a 24/10/2026)

A primeira versão juntou peças prontas: Ollama, Open WebUI, Qwen3 8B e embeddings Nomic, tudo local, com um acervo de documentos oficiais sobre água e alimentação.

Funcionou no primeiro teste e começou a falhar no segundo. Cada pergunta que dava errado ganhava um remendo: um sinônimo, uma palavra-chave, uma regra que bloqueava um método antes de buscar. Em três dias foram mais de 40 versões e uns 40 documentos de passagem de bastão. A candidata 0.11.8 foi congelada para teste sem nunca ser aprovada: acertava os testes conhecidos e errava a pergunta seguinte.

A lição que fica: remendo por frase é overfitting operacional. Ele melhora o caso do teste e quebra o próximo usuário.

## v2: medir antes de mexer (24/10/2026 em diante)

A v2 recomeçou com três regras:

1. **Corrigir categorias de erro, nunca frases.**
2. **Medir cada etapa separadamente**: a busca acha os trechos certos? O modelo escreve bem com eles?
3. **Começar simples** e só adicionar peça quando ela move o número.

| Fase | O que entrou | Resultado |
| --- | --- | --- |
| 1. Gabarito | 24 casos do dia a dia, com os trechos que respondem cada um | Busca simples (BM25): acha 63% em 20 resultados |
| 2. Busca | Embedding multilíngue (bge-m3) e reranker | 87% em 20; o embedding da v1 ficava no nível da busca simples |
| 3. Acervo | Títulos e texto corrigidos, PDFs de duas colunas legíveis | Top-5 entre 65% e 70% |
| 4. Conversa | O modelo quebra a pergunta em 2 a 4 buscas, 8 trechos por resposta | +4 a +6 pontos, nos dois turnos |
| 5. Resposta | Qwen3 8B com raciocínio e checagem de números por código | Cobertura de 54%, 19 s por resposta |
| 6. Validação | 20 dúvidas reais escritas sem olhar o acervo, rodadas uma vez só | Cobertura de 61%, mas 3 de 20 respostas perigosas |

## O que a validação ensinou

Nos casos de desenvolvimento, nenhuma resposta perigosa. Nas dúvidas inéditas, três, todas do mesmo tipo: a fonte diz "não use" e o modelo diz "trate e use". O conjunto de desenvolvimento tinha um caso só dessa família, e o ajuste resolveu aquele caso, não a família.

Uma rodada seguinte corrigiu uma das três. As outras duas seguem o padrão "não é seguro, mas, se quiser, faça assim": modelos treinados para ajudar resistem a dizer só "não". Prompt, raciocínio e pedir ao modelo que copie as proibições não bastaram. Isso aponta para uma mudança de estrutura, não para mais um ajuste.

## Onde estamos

O placar atual está no [README](README.md#onde-está-hoje). O próximo passo do projeto é atacar a família "quando não tratar" como categoria, e medir num conjunto de teste novo, que ainda não foi usado para nada.

A narrativa completa, com os tropeços, está no artigo de lançamento. Os conceitos de produto que apareceram no caminho estão em [APRENDIZADOS-AI-PM.md](APRENDIZADOS-AI-PM.md).
