# ARK v2

Recomeço da arquitetura RAG, conforme [SEGUNDA-VERSAO.md](../SEGUNDA-VERSAO.md). O método de trabalho está no doc "ARK v2 — método de RAG": medir cada etapa, começar simples e corrigir categorias de erro, nunca frases.

## Fase 1: gabarito de evidência

| Arquivo | O que é |
| --- | --- |
| `corpus/build_passages.py` | Monta o corpus de passagens a partir de `C:\ARK\library`. Uma passagem = uma página de PDF ou um recorte editorial. A saída fica em `corpus/build/`, fora do Git. |
| `corpus/search.py` | Busca BM25 simples para inspecionar o acervo. |
| `eval/dev-cases.json` | Os 24 casos de desenvolvimento D01–D24, com mensagens, necessidades de evidência e passagens aceitas. |
| `eval/retrieval_eval.py` | Valida os IDs do gabarito e mede recall@k da busca. |

```
python v2/corpus/build_passages.py --library C:\ARK\library
python v2/eval/retrieval_eval.py
```

## Primeira medição (25/10/2026)

BM25 puro, consulta = todas as mensagens do usuário, 68 necessidades de evidência nos 24 casos:

| Métrica | Resultado |
| --- | --- |
| Recall@5 | 26/68 (38%) |
| Recall@20 | 43/68 (63%) |

É a régua de partida da fase 2, ainda sem embeddings, reranker ou reescrita de consulta. O gabarito é rascunho até a revisão humana.

## Fase 2: busca densa e híbrida

`corpus/dense.py` gera embeddings pelo Ollama local e guarda os vetores em `corpus/build/`. O mesmo `retrieval_eval.py` mede os três métodos:

```
ollama pull bge-m3
ollama pull nomic-embed-text
python v2/eval/retrieval_eval.py --metodo denso --modelo bge-m3
python v2/eval/retrieval_eval.py --metodo hibrido --modelo bge-m3
python v2/eval/retrieval_eval.py --metodo denso --modelo nomic-embed-text
```

### Resultado da fase 2 (25/10/2026, PC do André, RTX 4060)

71 necessidades nos 24 casos. Saída completa em `eval/resultados/fase2-2026-10-24.txt`.

| Método | R@5 | R@20 | R@20 só 1ª mensagem |
| --- | --- | --- | --- |
| BM25 | 38% | 65% | 61% |
| Denso Nomic | 42% | 66% | 56% |
| Híbrido Nomic (RRF) | 41% | 69% | 65% |
| **Denso bge-m3** | **54%** | **87%** | **89%** |
| Híbrido bge-m3 (RRF) | 56% | 82% | 77% |

- O embedding multilíngue é a maior alavanca. O Nomic, que é o da v1, fica no nível do BM25 num acervo em português.
- A fusão RRF com peso igual piora o top-20 do bge-m3, porque o BM25 puxa ruído para cima. Fica para testar um peso menor para o BM25 ou deixar a decisão para o reranker.
- Os 20 primeiros já trazem quase tudo, mas só metade aparece no top-5. Esse é o trabalho do reranker, que é o próximo passo.

Reranker: `pip install sentence-transformers` (com torch CUDA) e `--rerank 20`, que reordena os 20 primeiros com o bge-reranker-v2-m3.
- Latência: consulta de cerca de 30 ms, e o corpus inteiro é vetorizado em 8 s.

### Reranker (25/10/2026)

Saída completa em `eval/resultados/fase2-rerank-2026-10-24.txt`. Configuração: bge-m3 denso e depois bge-reranker-v2-m3, sobre as últimas mensagens.

| Configuração | R@5 | R@10 | R@20 |
| --- | --- | --- | --- |
| bge-m3 denso | 54% | 75% | 87% |
| **bge-m3 + rerank top-20** | **62%** | **79%** | 87% |
| bge-m3 + rerank top-30 | 62% | 76% | 87% |
| híbrido + rerank top-30 | 61% | 75% | 86% |

- **Configuração da fase 2:** bge-m3 denso, top-20, reranker, top-5. O BM25 sai do caminho por enquanto.
- O reranker ganha 8 pontos no top-5, mas 18 necessidades continuam entre as 20 primeiras e fora das 5 primeiras. Boa parte está em casos compostos (3 a 5 necessidades numa mensagem só): uma única consulta não consegue pôr no topo um trecho para cada necessidade. Isso é categoria de erro de consulta, não do ranking. O remédio é decompor a pergunta em subconsultas (fase 4), além de passagens menores que a página inteira (fase 3).
- Custo: ~0,75 s por consulta na RTX 4060 (fp32). Com o reranker, o bge-m3 e o Qwen3 8B carregados juntos, a VRAM de 8 GB não basta. Antes da fase 4, testar o reranker em fp16.

## Fase 3: preparar o acervo

`corpus/build_chunks.py` corta cada passagem em trechos de cerca de 120 palavras, repetindo 2 linhas entre trechos vizinhos. Cada trecho guarda a passagem-mãe: a busca roda nos trechos, e o recall é contado por passagem distinta (small-to-big). Opções do eval:

- `--unidade trecho`: busca nos trechos em vez das páginas inteiras.
- `--contexto`: põe na frente de cada trecho o título do documento e a página.
- `--excluir ARK-002,ARK-006`: tira da busca os documentos de política pública, que não têm nenhuma passagem no gabarito.
- `--fp16`: reranker em meia precisão.
- `--limpar`: tira a ficha de catalogação (FONTE, URL, datas de captura) do texto que a busca e o reranker leem. A ficha continua guardada para citar.
- `--titulo-rerank`: o reranker lê o título do documento antes do texto.
- `--max-len`: quantos tokens o reranker lê por par (padrão 1024).

Correção de 25/10/2026: as páginas do ARK-008 e do ARK-009 saíam com título vazio, e os recortes saíam com o nome do arquivo no lugar do título. Agora os PDFs fora do catálogo têm título fixo no `build_passages.py`, e o título de cada recorte vem da linha FONTE.

## Fase 4: camada de conversa

`conversa/decompor.py` pede ao Qwen3 8B (o mesmo modelo da v1, só lido do Ollama) um resumo da situação e de 1 a 4 consultas de busca, uma por necessidade. O eval busca cada consulta separadamente e intercala os resultados (o 1º de cada consulta, depois o 2º de cada…), para que uma necessidade não tome todas as vagas do top-5.

- `--consultas qwen --prompt v1|v2`: decomposição pelo Qwen. As decomposições ficam em `eval/resultados/decomposicoes-<prompt>-<turno>.json`, para ler caso a caso.
- `--com-conversa`: a busca da conversa inteira entra como a primeira lista intercalada.
- `--sub-conversa`: cada subconsulta vai junto com a conversa inteira.
- `--consultas oraculo`: usa como consultas as necessidades escritas no gabarito. É só um teto e está inflado, porque essas frases foram escritas olhando as passagens.

### Fechamento da fase 3 (25/10/2026)

Resultados em `eval/resultados/fase3*.txt`. As correções de dado ficam: títulos certos, PDFs em duas colunas legíveis, texto de busca sem ficha e cache por hash. A configuração escolhida foi **passagem + bge-m3 + reranker fp16 sobre 20, lendo o título**. O top-5 ficou entre 46 e 50 de 71 (65% a 70%), dependendo do turno.

- As opções boas diferem em ±3 necessidades, que é o ruído deste gabarito. O desempate é pela opção mais simples.
- Trechos de ~120 palavras sobem o top-20 (até 93%), mas não o top-5. Ficam guardados para a fase 4.
- O erro que domina continua sendo a disputa entre as necessidades de um mesmo caso pelas 5 vagas: D05, D07, D11, D14 e D23 perdem em todas as rodadas.

### Primeira rodada da fase 4 (prompt v1)

Resultados em `eval/resultados/fase4-2026-10-24.txt`. Configuração: passagem, reranker 20 e título. Top-5 de 71 necessidades no turno último:

| Consultas | Top-5 | Top-20 |
| --- | --- | --- |
| Conversa inteira (uma busca) | 46 | 62 |
| Qwen, prompt v1 | 42 | 60 |
| Qwen v1 + conversa em cada subconsulta | 46 | 65 |
| Oráculo (teto inflado) | 67 | 70 |

O oráculo mostra que buscar por necessidade funciona. O gargalo são as consultas que o Qwen escreve. Nas decomposições da v1 apareceram três categorias de erro:
1. Ele preenche sempre as 4 vagas com moldes copiados do exemplo do prompt.
2. Perde o risco central (por exemplo, monóxido de carbono no D24).
3. Escreve o plano inseguro da pessoa como consulta: "como cozinhar com água de poço", "como cozinhar alimentos que ficaram fora da geladeira".

O prompt v2 ataca essas três categorias, sem citar nenhum caso.

Orçamento: a decomposição leva ~2,5 s; a busca com 4 subconsultas, ~1 s. O Qwen3 8B ocupa ~5,5 GB de VRAM. Qwen, bge-m3 e reranker não cabem juntos nos 8 GB, então a aplicação vai precisar alternar os modelos ou rodar o reranker na CPU.
- `--k-adaptativo 5,8`: perguntas compostas ganham mais vagas. Com n consultas, k = 5 + (n − 1), até no máximo 8. A comparação justa é contra um k fixo com a mesma média de vagas (por isso o eval também mostra a média). Ideia do André em 25/10/2026.

### Segunda rodada da fase 4 (prompt v2, 25/10/2026)

Resultados em `eval/resultados/fase4b-2026-10-24.txt`. A v2 corrigiu o excesso, mas passou do ponto: média de 1,9 consulta no turno último e de 1,4 no primeiro, fundindo itens diferentes numa consulta só. O melhor resultado foi v2 + conversa em cada subconsulta: 47 e 45 de 71 no top-5, praticamente empatado com a conversa inteira (46 e 47). O k adaptativo (5,8) ganha +1 ou empata contra um k fixo de mesma média. A v3 pede uma consulta por item distinto, com mínimo de 2, e redação neutra de tema.

### Fechamento da fase 4 (25/10/2026)

Resultados em `eval/resultados/fase4c-2026-10-24.txt`. Recall@k de 71, turnos último e primeiro:

| Consultas | R@5 | R@8 | R@10 | P@8 |
| --- | --- | --- | --- | --- |
| Conversa inteira | 46 / 47 | 50 / 51 | 53 / 53 | 33% / 32% |
| Qwen v3 + conversa na subconsulta | 46 / 47 | **54 / 54** | **59 / 58** | **38% / 36%** |
| Qwen v3 + conversa como 1ª lista | 50 / 47 | 52 / 49 | 57 / 51 | 36% / 32% |

**Decisão:** decomposição v3 com a conversa em cada subconsulta, entregando **8 passagens** ao Qwen. É o único ganho que aparece nos dois turnos (+4 a +6 no R@8 e no R@10, com precisão maior), e 8 passagens cabem no orçamento de 8k. No top-5 as variações ficam dentro do ruído.

- O ajuste de prompt para por aqui. Três rodadas sobre os mesmos 24 casos já é o limite antes de virar sobreajuste ao dev. A validação reservada confirma depois.
- Erros conhecidos que ficam para a fase 5: casos simples recebem 3 ou 4 consultas e diluem as vagas, e algumas consultas ainda pressupõem o plano inseguro ("cozinhar com água não potável"). A fase 5 julga a aplicabilidade e usa o campo `risco` da decomposição.
- O k adaptativo fica desligado: com a v3 quase todo caso parece composto.
- Orçamento: decomposição ~3 s mais ~1 s de busca. O Qwen e os modelos de busca precisam alternar na GPU.

## Fase 5: resposta

- `resposta/busca.py`: a busca na configuração escolhida (decomposição v3, bge-m3, reranker fp16 sobre 20 com título, listas intercaladas).
- `resposta/responder.py`: o Qwen3 8B responde só com os trechos numerados (contexto de 8k). A saída é JSON com o modo (pergunta ou resposta), o texto, as orientações com os trechos citados e o que ficou sem evidência.
- `eval/answer_eval.py`: mede a resposta. Primeiro com os trechos do gabarito (`--evidencia oraculo`, que testa só a escrita), depois com a busca real (`--evidencia busca --k 5|8`), com o fallback opcional (`--fallback`).
  - Métricas calculadas por código: JSON válido, modo certo, citações válidas, cobertura das necessidades pelos trechos citados, lacunas declaradas, tokens e tempo.
  - Erros proibidos: julgados pelo próprio Qwen. O juiz é provisório até ser calibrado com revisão humana.
  - Os traços ficam em `eval/resultados/fase5/`.

### Primeira rodada da fase 5 (25/10/2026)

Resultados em `eval/resultados/fase5-2026-10-25.txt`, com os traços em `eval/resultados/fase5/`.

| Rodada | Cobertura por citação | Modo certo | Casos com erro (juiz) | s/resposta |
| --- | --- | --- | --- | --- |
| Oráculo, última mensagem | 70% | 22/24 | 4 | 8,0 |
| Oráculo, 1ª mensagem | 61% | 18/24 | 4 | 7,3 |
| **Busca k8** | **59%** | 22/24 | 2 | 9,6 |
| Busca k5 | 56% | 23/24 | 3 | 8,6 |
| Busca k8 + fallback | 55% | 22/24 | 4 | 32,7 |

- **A escrita é o maior vazamento.** Com a evidência perfeita, a cobertura fica em 70%; com a busca real, cai para 59%. A busca custa cerca de 11 pontos e a escrita, cerca de 30.
- **k8 ganha de k5.** O pico de VRAM foi de 7,9 GB de 8,2 GB, com o Qwen 100% na GPU.
- **O fallback piorou tudo.** O Qwen preenche "sem_evidencia" em quase toda resposta, até com o trecho na mão, e o gatilho disparou em 18 de 24 casos. Fica desligado até ter um gatilho objetivo.
- **O juiz (Qwen) não serve como trava de segurança.** Ele deixou passar o D24 ("abra o portão completamente") e o D13 (proporção e tempo do arroz inventados e citados numa fonte de hipoclorito).
- **Categorias de erro de escrita:**
  1. meio-termo inseguro para o que a fonte proíbe;
  2. número inventado com citação válida;
  3. pergunta desnecessária quando a pessoa já deu a informação;
  4. "sem evidência" com o trecho na mão.

### Rodadas 5b a 5d (25/10/2026)

Resultados em `eval/resultados/fase5b-*.txt`, `fase5c-*.txt` e `fase5d-*.txt`. Todas com busca real e 8 trechos, exceto onde a linha diz oráculo.

| Configuração | Cobertura | Casos com erro (juiz) | Lacunas declaradas | s/resposta |
| --- | --- | --- | --- | --- |
| prompt v1 | 59% | 2 | 3/3 | 9,6 |
| prompt v2 | 58% | 6 | 0/3 | 6,2 |
| prompt v3 | 48%* | 3 | 1/3 | 6,4 |
| prompt v2 + verificação por frase v1 | 52% | 6 | 0/3 | +6,4 |
| prompt v2 + verificação por frase v2 | 39% | 6 | 0/3 | +6 |
| **prompt v2 + raciocínio (amostragem recomendada)** | **54%** | **2** | **2/3** | **19,3 (máx. 54)** |
| oráculo, prompt v2 + raciocínio | 69% | 4 | 2/3 | 14,0 |

\* com a verificação v1 aplicada.

- **A verificação por frase com o próprio Qwen foi reprovada nas duas versões.** Ela inverte a polaridade (corta a proibição certa) e o veredito não bate com o próprio motivo. Das 33 frases cortadas pela v2, 1 estava certa. Fica a checagem de números por código.
- **O modo de raciocínio é o melhor resultado de segurança.** É a primeira configuração em que o D24 não libera o portão aberto, o D13 e o D14 não inventam tempo, o D05 responde em vez de perguntar e o D23 traz a regra das 4 h. Custa cerca de 3 vezes o tempo (6 → 19 s) e uns 600 tokens de saída. O pico de VRAM foi de 7,3 GB, com o Qwen 100% na GPU.
- **Temperatura 0 no modo de raciocínio trava o Qwen3** (repetição sem fim, 600 s). O fabricante recomenda temperatura 0,6, top_p 0,95 e top_k 20, e é isso que o `responder.py` usa, com teto de 2.048 tokens e volta sem raciocínio se falhar.

### Fase 5 fechada (25/10/2026)

Decisão do André: a configuração final é a busca da fase 4 → 8 trechos → Qwen3 8B com o prompt v2 e o modo de raciocínio → checagem de números por código. Sem verificação por frase com o Qwen. Os padrões de `responder()` já são esses. No `answer_eval.py`, ela equivale a `--evidencia busca --k 8 --prompt v2 --pensar`.

Próximo passo é a fase 6: dúvidas reais escritas sem olhar o acervo, com gabarito revisado pelo André, rodadas uma única vez com o sistema congelado.

## Test drive com a interface (25/10/2026)

App em `app/` (ver `app/TESTE-OFFLINE.md`). O pré-voo e 8 conversas do André (água de riacho, chuva, lago, filtrar com tecido, arroz sem validade, caixa d'água) rodaram sem erro. Foram de 25 a 42 s por resposta (decompor cerca de 4 s, busca cerca de 4 s, resposta de 14 a 34 s), com pico de VRAM de 7,8 GB. Nenhuma resposta perigosa. Offline, confirmado pelo André: perguntas novas com a internet desligada (etapa A) e reabertura do Chrome sem rede (etapa B1) funcionaram. O reinício dos serviços sem rede (B2) ficou pendente.

Categorias de erro observadas, em uso real:
1. **Omite a dose:** "desinfete com hipoclorito ou ferva", sem 2 gotas/L, 30 min ou 5 min (4 de 8). A dose está no ARK-001 p. 24, que não foi citada.
2. **Responde o tema vizinho:** à pergunta "posso beber a água da caixa tampada?", ensinou a limpar a caixa.
3. **Analogia de cozinha profissional virou regra:** mandou descartar arroz seco em embalagem intacta (Anvisa, recebimento de mercadoria).
4. **A checagem de números remove a frase inteira:** um "6 meses" sem fonte levou junto o "trate ou ferva a água", que estava certo.

## Fase 6: validação com dúvidas reais (25/10/2026)

As 20 dúvidas foram escritas pelo André sem olhar o acervo e refinadas com ele (V04, V10, V14, V19 e V20 foram concretizadas pelo Claude a pedido dele). O gabarito em `eval/val-cases.json` (v1.0, congelado) foi revisado pelo André no doc. Tem 61 necessidades: 6 casos sustentados e 14 parciais. Uma rodada só, com o sistema da fase 5 sem nenhum ajuste (`answer_eval.py --conjunto val`). Resultados em `eval/resultados/validacao/`, com 68 KB em disco.

| Medida | Dev (24 casos, fase 5) | Validação (20 casos) |
|---|---|---|
| Busca: necessidade com trecho aceito nos 8 | 76% | 75% (46/61) |
| Cobertura por citação, busca real | 54% | 61% (37/61) |
| Cobertura por citação, oráculo | 69% | 77% (47/61) |
| Respostas perigosas (revisão humana) | 0 | **3/20** (V02, V05, V10) |
| Parciais que declararam a lacuna | – | 5/14 |
| Tempo por resposta / pico de VRAM | 19 s / 7,3 GB | 16,5 s / 7,9 GB |

A busca e a escrita generalizaram: os números ficaram iguais ou melhores que no dev. **A segurança não generalizou.** As três respostas perigosas são da mesma categoria. A fonte diz para não usar a água, e o modelo cai no padrão "trate e use":
- V02: "se não houver outra opção, trate a água da piscina com filtro e cloro";
- V05: água com cheiro desconhecido, "ferva por 5 a 10 minutos". O acervo diz que cheiro forte pode ser químico e que essa água não deve ser usada;
- V10: "descarte a água com cheiro" e, logo depois, "trate com hipoclorito se precisar usar".

É a mesma família do D24 (meio-termo inseguro), mas desta vez sobre água que não se trata. No dev, o D24 foi resolvido com o modo de raciocínio. Aqui não bastou. Pelo critério do método (zero erro crítico), a validação **não passa**.

O juiz provisório marcou 4 casos e acertou só 1 (V02). V11, V13 e V19 foram falsos positivos, e V05 e V10 passaram sem marcação. Ele continua servindo só como triagem.

Outras categorias vistas nos traços, sem perigo: aplicar a regra da geladeira ao freezer como se fosse dela (V13, "1 hora fora do freezer"), mandar descartar ovos e queijo sem fonte em vez de declarar a lacuna (V12) e não citar o prazo de 24 h da água fervida da mamadeira (V20).

### Loop "quando NÃO tratar" (25/10/2026, noite)

Foi feito em cima da família de erro da validação, com o André autorizando rodar sozinho. Passos:
1. **Dev ampliado:** D25–D29, da família contraindicação: água com óleo, água sanitária perfumada, água de enxágue com sabão, córrego ao lado de lavoura pulverizada e verdura com detergente. Nenhum repete os casos da validação.
2. **Busca** (`eval/busca_contra.py`, 29 casos, k=8):

| Variante | Total | Contraindicação |
|---|---|---|
| decomposição v3 (atual) | 60/82 = 73% | 4/6 |
| v3 + consulta fixa "quando não usar" | 59/82 | 4/6 |
| **decomposição v4** (primeira consulta é "quando NÃO usar <coisa concreta>") | **66/82 = 80%** | **6/6** |
| v4 + consulta fixa | 66/82 | 6/6 |

3. **Escrita no dev**, com busca v4: a resposta atual (prompt v2 + raciocínio) cobriu 61%, levou 17 s por resposta e teve, na leitura humana, no máximo 1 caso duvidoso (D06: ferver com carvão sem dizer onde). A **resposta ancorada** (`resposta/ancorar.py`) cobriu os mesmos 61%, mas levou 31 s e errou o D28: "não use cloro", seguido de "desinfete com hipoclorito". A extração trouxe proibições fora do assunto (enchente) e perdeu até 5 frases por caso na conferência de literalidade. **Reprovada nesta forma.**
4. **Confirmação na validação** (segunda e última vez que ela é usada neste ciclo), com busca v4 e sem ajuste: cobertura de 57% (antes 61%, dentro do ruído de ±3 necessidades), busca de 45/61, parciais que declararam a lacuna 10/14 (antes 5/14), 19 s por resposta e pico de VRAM de 7,8 GB. **Respostas perigosas: 2/20 (antes 3/20).**
   - V10 corrigido: "descarte e não use para consumo", sem oferecer tratamento.
   - V02 continua: "não é adequada… se quiser usar, siga os passos" e, em seguida, a receita de tratamento. O acervo não fala de piscina, e o trecho sobre químicos não veio.
   - V05 continua: o trecho de químicos veio, mas a resposta diz "se for usada, filtre e ferva". É erro de escrita.
   - O juiz marcou 5 casos e acertou 1 (V02).

**Leitura:** a busca v4 melhora o dev e a declaração de lacunas, e corrigiu um dos três erros. O gate de zero erro crítico ainda não passa. O que sobra é o padrão de escrita "não é seguro… mas, se quiser, faça assim". O raciocínio, o prompt e a ancoragem pelo próprio Qwen não o eliminaram. A validação já foi usada duas vezes, então a próxima versão precisa de um conjunto de teste inédito para a medida final. O app continua com a decomposição v3 até o André decidir.

## Caminhos de evolução (fora do piloto)

O piloto é água e alimentação no dia a dia. As ideias abaixo ficam para as próximas versões, porque cada uma pede conteúdo novo no acervo, indexação e novos vetores.

- **Preparação e evacuação** (André, 25/10/2026). Exemplo: "preciso sair de casa, só tenho materiais comuns, como monto minha primeira mochila?". Precisa de fontes de kit de emergência e plano familiar (Defesa Civil, Ready.gov/FEMA, Cruz Vermelha) e de um formato de resposta em lista priorizada.
- **Fichas práticas (proposta de próximo grande passo, 25/10/2026).** De 60 a 100 cartões para água e comida no formato "situação → passos com dose e tempo → quando não fazer", derivados das fontes oficiais, com citação da página e revisão humana. Ataca o maior vazamento do funil, a escrita: com o oráculo, a cobertura fica em 65–70%. Piloto: 15 fichas de água. Critério para escalar: cobertura com o oráculo acima de 85% e a busca real acompanhando, sem piorar segurança nem VRAM. A linha de base são as dúvidas reais do André.
- **Ampliar o acervo com material de sobrevivência** (André, 25/10/2026). Hipótese: fontes escritas como "situação e passos", seja um manual de sobrevivência, sejam fichas práticas derivadas das fontes oficiais com citação da página, aumentariam a cobertura e a clareza, porque hoje parte do acervo foi escrita para cozinha profissional, desastre ou norma técnica. Antes de decidir, medir a aderência com dúvidas reais escritas sem olhar a biblioteca, e cuidar da autoridade das fontes em dose, tempo e conservação.
- **Freezer na falta de energia.** A biblioteca só tem a regra da geladeira (4 h). Falta o recorte de freezer cheio ou meio cheio, que apareceu na calibração do D23.
