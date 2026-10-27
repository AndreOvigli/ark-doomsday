# Aprendizados de AI PM no ARK

Registro vivo dos conceitos que aparecem no desenvolvimento do ARK, explicados em linguagem de produto. Cada entrada diz o que é, por que importa e onde apareceu no projeto. Novas entradas entram no fim de cada seção.

## RAG e busca

### RAG (Retrieval-Augmented Generation)
**O que é:** o modelo não responde só com o que "lembra". Antes, o sistema busca trechos de documentos e entrega esses trechos ao modelo, que escreve a resposta apoiado neles.
**Por que importa:** é o que permite citar fonte e limitar a resposta ao acervo. Mas a qualidade final nunca passa da qualidade da busca: se o trecho certo não chega, o modelo não tem como acertar.
**No ARK:** a v1 já era RAG; o problema estava nas camadas em volta da busca, não na ideia.

### Recall@k
**O que é:** de todos os trechos que deveriam ter sido encontrados para uma pergunta, quantos apareceram entre os k primeiros resultados.
**Por que importa:** é o funil de cima da resposta. Se o recall@5 é 60%, em 4 de cada 10 perguntas o modelo responde sem a evidência certa, por melhor que seja o prompt.
**No ARK:** métrica principal das fases 2 e 3 da v2.

### Busca híbrida
**O que é:** combinar busca por palavra (BM25, boa para termos exatos como "hipoclorito") com busca por significado (embeddings, boa para "não tenho panela" achar "recipiente resistente ao calor").
**Por que importa:** cada uma cobre o ponto cego da outra. A fusão (RRF) junta os dois rankings.
**No ARK:** a v1 já usava BM25 + Nomic com RRF.

### Medir antes de assumir: "híbrido sempre ganha" não é lei
**O que é:** a literatura recomenda combinar busca por palavra e por significado. No ARK, a combinação com peso igual piorou o top-20 do melhor embedding (87% caiu para 82%).
**Por que importa:** boa prática é hipótese, não verdade. O gabarito existe justamente para uma regra geral não virar decisão sem teste. A maior alavanca era outra: trocar o embedding inglês (Nomic, 66%) pelo multilíngue (bge-m3, 87%).
**No ARK:** fase 2, em 25/10/2026.

### Reranker
**O que é:** um segundo modelo, mais lento e mais preciso, que relê só os ~20 candidatos da busca e reordena, comparando pergunta e trecho lado a lado.
**Por que importa:** a busca é boa para não perder nada (recall@20 alto), mas ruim para pôr o melhor em cima. O modelo que responde só lê os primeiros, então a ordem é o que chega ao usuário.
**No ARK:** com o bge-m3, o top-20 já tem 87% das evidências, mas o top-5 só 54%. Fechar essa diferença é o trabalho do reranker.

### Pergunta composta pede consulta decomposta
**O que é:** quando a pessoa pede três coisas numa mensagem ("beber, cozinhar e guardar"), uma busca só tende a trazer trechos bons para a necessidade dominante e fracos para as outras. Decompor quer dizer quebrar a pergunta em subconsultas, uma por necessidade, e juntar os resultados.
**Por que importa:** nem reranker resolve isso, porque ele só reordena o que a consulta trouxe. É um erro de categoria de consulta, não de ranking. Identificar a categoria certa evita gastar esforço na etapa errada.
**No ARK:** na fase 2, 18 necessidades estavam entre as 20 primeiras e fora das 5 primeiras, concentradas em casos compostos. A correção fica para a camada de conversa (fase 4).

### Separar o que a busca lê do que a resposta cita
**O que é:** cada trecho tem duas partes: o conteúdo (o que responde) e a ficha de catalogação (fonte, URL, data). A busca e o reranker devem ler só o conteúdo. A ficha fica guardada ao lado e volta na hora de citar.
**Por que importa:** metadado grudado no texto vira ruído. O embedding mistura "Ministério da Saúde, 2023" no sentido do trecho, e o reranker gasta atenção lendo URL. É qualidade de dado, não de modelo: um modelo melhor não conserta dado mal preparado.
**No ARK:** na fase 3, os recortes traduzidos começavam com FONTE/URL/datas, e os PDFs da Anvisa e do MS estavam sem título. Os dois foram corrigidos na preparação do acervo.

### O índice: a "planilha" por trás da busca
**O que é:** o acervo preparado fica numa tabela. Cada linha é um trecho (chunk), e as colunas guardam o que cada etapa precisa. Exemplo real do ARK v2, com os textos encurtados:

| id | página-mãe | título | conteúdo (o que a busca lê) | ficha (o que a resposta cita) | vetor (bge-m3) |
| --- | --- | --- | --- | --- | --- |
| `ARK-001#p024~c01` | `ARK-001#p024` | Água tratada em casa (MS, 2026) | "Prepare a água. Recomenda-se que a água tenha sido filtrada. Se estiver barrenta… deixe descansar…" | Ministério da Saúde, p. 24 | [0,012; −0,031; …] (1024 números) |
| `ARK-001#p024~c02` | `ARK-001#p024` | Água tratada em casa (MS, 2026) | "Guarde a água tratada em recipiente limpo e tampado. Consuma em até 24 horas." | Ministério da Saúde, p. 24 | [0,044; 0,007; …] |
| `ARK-008#p030~c01` | `ARK-008#p030` | Anvisa. Cartilha de Boas Práticas | "Não use e não compre produtos com embalagens amassadas, estufadas, enferrujadas…" | Anvisa, p. 30 | [−0,020; 0,015; …] |
| `ARK-009#…latas-estufadas~c01` | `ARK-009#…latas-estufadas` | MS. Evite mais riscos… água e alimentos | "Alimentos em latas, PET, vidros… com inchaço, esmagamento, vazamento… devem ser descartados" | MS, set/2023, p. 9 (recorte conferido) | [0,038; −0,002; …] |

**Quem usa cada coluna:**
- **BM25:** lê o *conteúdo* e conta palavras.
- **Embedding:** gerou o *vetor* a partir do *conteúdo*, uma vez, na preparação. Na busca, só compara vetores.
- **Reranker:** lê *título + conteúdo* ao lado da pergunta.
- **Recall do gabarito:** conta pela *página-mãe*. Dois trechos da mesma página ocupam uma vaga só.
- **Qwen:** recebe *conteúdo + ficha*, e às vezes a página-mãe inteira (small-to-big), para responder e citar.

**Por que importa:** os modelos só fazem a parte de "entender" (vetor, nota, resposta). Quem decide o que cada um vê é a preparação dos dados. Por isso erro de coluna, como título vazio ou ficha misturada no conteúdo, derruba a qualidade sem que nenhum modelo esteja "errado".
**No ARK:** gerado por `v2/corpus/build_passages.py` (passagens) e `v2/corpus/build_chunks.py` (trechos). Os vetores ficam em cache em `v2/corpus/build/`, fora do Git.

### Chunking: regra fixa ou interpretação
**O que é:** o corte em trechos pode ser uma regra fixa (a cada ~120 palavras), seguir a estrutura do documento (títulos, seções, listas) ou usar um modelo para decidir onde um assunto termina ou para escrever uma frase de contexto para cada trecho ("contextual retrieval").
**Por que importa:** regra fixa é barata, previsível e boa como linha de base, mas corta no meio de uma lista ou de uma tabela. Corte por estrutura ou por modelo custa mais e só vale se o gabarito mostrar ganho.
**No ARK:** hoje a regra é fixa e deliberada, para ter um baseline. O PDF da Anvisa tem duas colunas ("O que fazer? / Por que fazer?"), e a extração atual as mistura linha a linha. Esse é o primeiro candidato a corte por estrutura.

### RAG corretivo: aproveitar o top-20 quando o top-5 falha
**O que é:** em vez de buscar uma vez e responder, o sistema confere se a evidência cobre cada necessidade. Se faltar, faz uma busca dirigida só para o que falta e puxa os próximos candidatos já ordenados pelo reranker, e não candidatos aleatórios.
**Por que importa:** quando o top-20 acerta muito mais que o top-5, existe evidência boa "na fila". O fallback aproveita essa evidência sem inflar todas as respostas. Num tema de segurança, evidência de fila é mais fraca e a resposta precisa dizer isso.
**No ARK:** ideia do André em 25/10/2026. Entra no desenho da fase 5 junto com dar mais vagas ao Qwen (contexto maior que 4096). O botão "não resolveu" do usuário fica para depois do test drive.

### Chunking e small-to-big
**O que é:** como o documento é cortado em pedaços para a busca. Small-to-big significa buscar em pedaços pequenos (precisos) e entregar ao modelo a seção inteira onde o pedaço está (completa).
**Por que importa:** pedaço pequeno demais chega sem contexto ("ferva por 5 minutos" sem dizer que antes precisa filtrar); grande demais dilui a busca.

### Embedding
**O que é:** um modelo que transforma um texto numa lista de números (vetor) que representa o significado. Textos de sentido parecido ficam com vetores próximos.
**Por que importa:** é o que faz a busca por significado funcionar ("não tenho panela" acha "recipiente resistente ao calor"). Ele não escreve a resposta, só organiza a busca. Modelo treinado mais em inglês tende a entender pior um acervo em português.
**No ARK:** a v1 usa o Nomic. A fase 2 compara o Nomic com o bge-m3 (multilíngue) no mesmo gabarito.

### Modelo vs. programa que roda o modelo (runtime)
**O que é:** o modelo é o "cérebro" (Llama da Meta, Qwen da Alibaba, bge-m3). O runtime é o programa que carrega e serve esse modelo no computador (Ollama). Ollama não é Llama: o nome só brinca com ele.
**Por que importa:** trocar de modelo não exige trocar de runtime, e vice-versa. É como o Steam e os jogos instalados nele.
**No ARK:** o Ollama roda o Qwen3 (respostas) e o Nomic (busca) na v1. Para testar o bge-m3 sem mexer na v1, subimos uma segunda cópia do Ollama fora de C:\ARK.

### Janela de contexto custa memória e tempo, não disco
**O que é:** a janela de contexto é quanto texto o modelo lê de uma vez. Aumentá-la não muda o tamanho do modelo no disco. Ela custa memória de vídeo (o KV cache, ~0,15 MB por token no Qwen3 8B) e tempo de leitura antes da primeira palavra da resposta.
**Por que importa:** num produto offline em hardware limitado, cada ganho de qualidade tem um preço em recurso. Medir os dois juntos evita uma versão "melhor" que não roda no aparelho alvo.
**No ARK:** premissa do André em 25/10/2026: a arca precisa ser leve, mas isso não bloqueia a evolução. A partir da fase 5, toda medição sai com o orçamento de disco, o pico de VRAM e o tempo por resposta.

Medido no PC do André (RTX 4060, 8 GB), com o qwen3:8b:

| Contexto | Memória do modelo | Coube na GPU? |
| --- | --- | --- |
| 2.048 | 4,9 GB | sim |
| 4.096 | 5,2 GB | sim |
| 8.192 | 5,8 GB | sim |
| 16.384 | 7,3 GB | não, transborda para RAM/CPU (fica lento) |
| 32.768 | 9,6 GB | não |

Cinco passagens cabem em 4k, e dez pedem 8k. O contexto vira um orçamento explícito do produto.

## Avaliação

### Recall vs. precision
**O que é:** o recall@k olha para o gabarito: das informações de que a resposta precisa, quantas apareceram nos k primeiros. A precision@k olha para a entrega: dos k trechos entregues, quantos servem para alguma coisa. Na pescaria, é "quantos dos peixes que eu queria eu peguei" contra "quanto da rede é peixe e quanto é lixo".
**Por que importa:** as duas puxam em direções opostas. Aumentar o k quase sempre sobe o recall e derruba a precision. No ARK, faltar evidência (dose, prazo, proibição) é mais grave que vir um trecho inútil, então o recall manda. A precision também pesa, porque trecho inútil gasta o orçamento de contexto e distrai um modelo de 8B.
**No ARK:** os números de "top-5" das fases 2 a 4 são recall@5. A precision@k entrou no eval em 25/10/2026, para avaliar o k adaptativo com os dois lados do trade-off.

### Avaliação por etapa (e não só pelo resultado final)
**O que é:** medir separadamente se a busca trouxe o trecho certo, se o modelo julgou a aplicabilidade certo e se a resposta ficou fiel ao trecho.
**Por que importa:** com só uma nota final você sabe que errou, mas não onde. É a diferença entre um funil de conversão por etapa e só olhar a receita do mês.
**No ARK:** a v1 media só a conversa final, e por isso cada falha virava remendo no lugar errado.

### O RAG como funil de conversão
**O que é:** a resposta final é o fim de um funil. Cada etapa tem a sua métrica, e a de cima é teto da de baixo. Mapa do ARK v2 em 25/10/2026, com 71 necessidades nos 24 casos de dev:

| Etapa | Pergunta da métrica | Número |
| --- | --- | --- |
| 1. Qwen escreve as consultas | as consultas cobrem as necessidades? | teto (oráculo) 67/71 no top-5 |
| 2. Embedding bge-m3, top-20 | o trecho certo entrou entre os 20? | ~88% |
| 3. Reranker, 8 trechos ao Qwen | o trecho certo ficou entre os 8? | 76% (54/71) |
| 4. Qwen responde | usou e citou certo o que recebeu, sem erro proibido? | fase 5 |

**Por que importa:**
- O que uma etapa perde, as seguintes não recuperam. O reranker não acha o que não veio nos 20, e o Qwen não cita o que não veio nos 8.
- Otimizar uma etapa isolada pode piorar o fim (mais trechos sobem o recall e podem distrair o modelo). A métrica final decide.
- Diferente de um funil comum, este tem volta: o fallback deixa a etapa 4 pedir mais material à etapa 3.

**No ARK:** a analogia é do André. É o mapa que decide onde atacar cada erro.

### Gabarito de evidência (golden set)
**O que é:** para cada pergunta de teste, a lista de trechos do acervo que a responde, marcada por humano antes de rodar o sistema.
**Por que importa:** é a régua da busca. Sem ele, "a busca está boa" é opinião; com ele, vira recall medido.
**No ARK:** fase 1 da v2, para os casos D01–D24.

### Teste do oráculo
**O que é:** entregar ao modelo os trechos do gabarito diretamente, pulando a busca.
**Por que importa:** separa as culpas. Se a resposta falha mesmo com o trecho certo na mão, o problema é geração; se acerta, o problema é a busca.

### Separar desenvolvimento, validação e teste
**O que é:** casos que a equipe usa para ajustar o sistema (dev), casos guardados para checar versões congeladas (validação) e casos nunca vistos para a medição final (teste).
**Por que importa:** é o mesmo princípio de não avaliar uma campanha com o público que você usou para desenhá-la. Melhorar nos casos que você já conhece não prova que generaliza.
**No ARK:** a v1 misturou isso, e os ganhos nos exemplos corrigidos não se repetiam em casos novos.

### O gabarito define o produto
**O que é:** os casos de teste não são neutros. Os escolhidos viram o alvo que o sistema vai otimizar.
**Por que importa:** com caso de borda demais (desastre, tragédia), o sistema fica bom no raro e mediano no que o usuário vive todo dia. O escopo do eval precisa espelhar o escopo do produto.
**No ARK:** em 25/10/2026 André tirou o caso de enchente do conjunto dev. O foco do piloto é sobrevivência no cotidiano (sem água encanada, sem luz, sem gás); tragédias ficam para um segundo nível.

### Resolução do gabarito: quando a diferença vira ruído
**O que é:** um conjunto de teste pequeno só separa mudanças grandes. Com 71 necessidades, cada necessidade vale cerca de 1,4 ponto percentual. Uma diferença de 1 a 3 necessidades entre duas configurações pode ser só sorte de quais casos foram escolhidos.
**Por que importa:** é o mesmo problema de um teste A/B com amostra pequena: dá para ver efeitos grandes (Nomic 66% contra bge-m3 87%), mas não para escolher entre opções quase iguais. Nesse ponto, ou se aumenta o conjunto, ou se escolhe a opção mais simples e barata entre as empatadas.
**No ARK:** na fase 3, as melhores configurações ficaram entre 48 e 49 de 71 no top-5. A decisão passa a ser pela simplicidade, e a validação reservada confirma depois.

### Citação válida não é evidência que sustenta
**O que é:** uma citação "válida" só prova que a resposta apontou para um trecho que existe. Não prova que o trecho diz aquilo. O modelo pode escrever uma informação inventada e pendurar nela a fonte mais próxima.
**Por que importa:** quem lê vê a fonte e confia mais, então a citação errada é pior que a ausência de citação. Contar citações válidas dá 100% e esconde o problema.
**Como medir sem humano:** para o que é verificável por código, verifique por código. Todo número da resposta (dose, tempo, quantidade, com a unidade) tem que estar escrito no trecho citado. Se não está, a frase sai e vira lacuna declarada. Custa milissegundos e nenhuma memória.
**No ARK (25/10/2026):** o D13 citava a página do hipoclorito para "1 litro de água por 100 g de arroz, 15 a 20 minutos", e o D14 inventava tempos de cozimento de feijão. O juiz (o próprio Qwen) deixou passar. A checagem pegou as duas categorias e custou 1 ponto de cobertura.

### Frequência e gravidade pedem conjuntos de teste diferentes
**O que é:** casos comuns medem a qualidade do produto, e uma resposta parcial ainda vale nota. Casos raros e graves funcionam como trava: a tolerância é zero, mas eles não devem guiar a otimização do dia a dia.
**Por que importa:** se você mistura os dois, ou o caso raro some na média (e o erro grave passa), ou ele domina os ajustes (e você otimiza o produto para algo que quase ninguém pergunta). Antifraude e moderação de conteúdo funcionam do mesmo jeito.
**No ARK (25/10/2026):** o André apontou que quase ninguém vai fazer churrasco na garagem (D24). Ele está certo sobre a frequência, mas a crença "com o portão aberto ventila" é comum e mata. O D24 vira família de segurança, medida à parte como trava, e o prompt não é ajustado por ele.

### Viés de seleção do gabarito: casos escritos olhando o acervo
**O que é:** quando quem escreve os casos de teste conhece a base de conhecimento, os casos tendem a caber nela. A cobertura medida fica otimista, porque o teste nunca pergunta o que a base não tem.
**Por que importa:** o usuário real não leu a biblioteca. A pergunta "o acervo cobre o que as pessoas precisam?" só se responde com dúvidas escritas por quem não viu o acervo. Esse é um teste de aderência do conteúdo, separado do teste do sistema.
**Cobertura vs. clareza:** são dois problemas diferentes. Faltar fonte é cobertura. Ter a fonte, mas escrita para outro público (cozinha profissional, desastre, norma técnica), é clareza, e cobra do modelo uma tradução onde ele erra. Para clareza, uma saída é ter fichas práticas derivadas das fontes oficiais, em formato de situação e passos e com citação da página. A saída não é trocar por fonte menos rigorosa.
**No ARK (25/10/2026):** com as consultas ideais, 67 de 71 necessidades têm evidência no acervo, mas os 24 casos foram escritos a partir dele. Próximo passo proposto: cerca de 20 dúvidas reais escritas sem olhar a biblioteca.

### O modelo não é um bom fiscal de si mesmo
**O que é:** pedir ao mesmo modelo pequeno que confira a própria resposta, frase por frase, parece barato e lógico. Na prática, ele erra a tarefa de conferir de um jeito diferente do jeito que erra a de escrever.
**No ARK (25/10/2026):** a verificação por frase com o Qwen 8B foi reprovada em duas versões. Ela marcava "contradiz" quando a frase e a fonte proibiam a mesma coisa, e cortava justamente as proibições certas. Na versão com perguntas de sim ou não, o veredito saía contrário ao próprio motivo. De 33 cortes, 1 estava certo.
**O que funcionou:** (1) checagem por código onde dá (números); (2) dar ao modelo tempo para raciocinar *antes* de escrever. O modo de raciocínio foi a primeira configuração a não liberar o carvão na garagem, ao custo de 3 vezes o tempo.
**Lição de PM:** prevenir na origem costuma ganhar de filtrar depois, e um filtro também precisa de gabarito antes de virar trava.

### Parâmetro de geração faz parte do produto
**O que é:** temperatura e amostragem não são detalhe técnico. Cada modo do modelo tem sua faixa recomendada.
**No ARK:** com temperatura 0, que é ótima para respostas diretas, o modo de raciocínio do Qwen3 entrava em repetição sem fim e travava por 10 minutos. Com a amostragem recomendada pelo fabricante, ficou estável, com máximo de 54 s.

### Hipóteses por etapa do funil
**O que é:** para cada etapa do funil, uma hipótese de evolução escrita antes do teste, que nasce de uma categoria de erro vista nos traços:
> *Se* [mudança] *na etapa* [X], *então* [métrica da etapa] *sobe de* a *para* b, *sem piorar* [métrica final e guardrails]. *Evidência:* [categoria de erro nos traços].

**Regras:**
1. Uma métrica final manda: no ARK, respostas certas, citadas e sem erro proibido. Ganho de etapa que não move o final não conta.
2. Guardrails fixos: erro crítico igual a zero e orçamento de VRAM, tempo e disco. Hipótese que estoura guardrail é rejeitada, mesmo que melhore a qualidade.
3. Ataque o maior vazamento primeiro, e escreva a hipótese para a categoria de erro, nunca para o caso.

**Exemplo do ARK (25/10/2026):** se o Qwen escrever uma consulta por item distinto (etapa 1), o recall com 8 trechos sobe de 50 para mais de 52, sem passar de 4 s. Evidência: o prompt v2 fundia "arroz, feijão e farinha" numa consulta só. Resultado: 54. Confirmada.

### Validação mostra o que o dev escondeu
**O que é:** o conjunto de validação é escrito sem olhar o sistema e rodado uma vez, sem ajuste. Ele mede se o que você corrigiu foi a categoria ou só os casos que você conhecia.
**No ARK (25/10/2026):** busca e escrita se mantiveram (cobertura de 54% no dev contra 61% na validação), mas apareceram 3 respostas perigosas em 20, contra 0 no dev. As três são "a fonte diz para não usar e o modelo diz para tratar e usar" (piscina, água com cheiro, água guardada que estragou). O dev tinha só um caso dessa família (D24), e o raciocínio resolveu aquele caso, não a família.
**Lição de PM:** número bom no dev é hipótese, não resultado. O gate de segurança precisa de vários casos por família de risco, senão você fecha o bug e deixa a categoria aberta.

### O "mas, se quiser…" do modelo
**O que é:** modelos treinados para ajudar resistem a dizer só "não". Mesmo quando escrevem "não é seguro", tendem a emendar um caminho para fazer assim mesmo. É um viés de prestatividade: o modelo prefere entregar algum procedimento a deixar a pessoa sem nenhum.
**No ARK (25/10/2026):** a busca nova passou a trazer o trecho "isso não se trata" (contraindicação de 4/6 para 6/6 no dev) e corrigiu um dos três casos. Nos outros dois, a resposta disse "não é adequada" e depois deu a receita. Pedir no prompt, dar tempo para raciocinar e fazer o próprio modelo copiar as proibições não bastou.
**Lição de PM:** quando a regra é de segurança e o modelo a quebra de forma sistemática, ela tende a sair do prompt e virar produto: uma regra fixa, uma ficha ou uma trava, decidida por quem responde pelo risco.

## Trade-offs e decisões de produto

### Corrigir categorias, nunca frases
**O que é:** quando o sistema erra, a correção precisa atacar o tipo de erro (por exemplo, "não percebe que o recurso acabou") e melhorar vários casos, nunca a frase específica que falhou.
**Por que importa:** remendo por frase dá vitória no caso de teste e quebra no próximo usuário. É overfitting operacional.
**No ARK:** regra aprovada para a v2 em 24/10/2026, depois dos sinônimos e âncoras por palavra da v1.

### Contexto do usuário molda a busca, não bloqueia
**O que é:** o que a pessoa conta (recursos, restrições) serve para reformular a busca e para julgar o que se aplica depois que os documentos chegam, e não como filtro que impede a busca.
**Por que importa:** filtrar antes esconde do modelo justamente a informação que poderia dizer "isso dá para fazer de outro jeito".
**No ARK:** a v1 bloqueava métodos por requisitos de recurso antes de buscar.

### Peso da interface também é orçamento de hardware
**O que é:** num produto que precisa rodar offline em máquina fraca, cada asset da interface (fonte, imagem, script) disputa o mesmo disco e a mesma memória que o modelo usa.
**No ARK (26/10/2026):** a fonte de terminal pesava 192 KB, mais que o app inteiro. Cortada para os caracteres latinos e comprimida, caiu para 16 KB com o mesmo visual.
**Lição de PM:** antes de discutir modelo menor, olhe o que está gordo em volta dele. Elementos decorativos (slogan, rótulos de "fósforo verde") também custam atenção numa tela que precisa passar risco com clareza.

### Em open source de RAG, o motor é o produto e o acervo é de cada um
**O que é:** num projeto aberto de RAG, quem entra traz o próprio acervo. O que se compartilha é o motor (busca, escrita, avaliação) e o método para montar um acervo confiável.
**Por que importa:** reproduzir o acervo de outra pessoa byte a byte sai caro. As fontes mudam, alguns sites bloqueiam o download e a extração de texto varia.
**No ARK (26/10/2026):** num build do zero, 12 dos 52 trechos do gabarito sumiram. A saída foi publicar o método (um guia de como escolher fontes confiáveis) e pedir que cada PR mostre o antes e o depois no mesmo acervo.
**Lição de PM:** número absoluto não se compara entre acervos; a diferença, sim.
