# ARK / Doomsday — decisões para a segunda versão

Registro de planejamento de 24 de outubro de 2026, consolidado a partir do chat **“Redefinir estrutura RAG do Doomsday”**. A expressão segunda versão identifica o recomeço arquitetural; não atribui um número de release ao código existente.

## Decisão de recomeçar

Foi decidido recomeçar pelo contrato de funcionamento, antes de escrever código. A arquitetura deve utilizar o modelo para compreender linguagem natural, preparar buscas e construir respostas fundamentadas.

As fontes originais, a proveniência, as avaliações e os exemplos de falha da primeira versão continuam úteis. A camada acumulada de regras de decisão fica como material histórico, sem obrigação de reaproveitamento.

| Problema observado | Direção definida |
|---|---|
| Correções por palavras e formulações conhecidas | Compreensão semântica da necessidade e avaliação de situações variadas. |
| Blocos documentais usados como respostas prontas | Síntese construída para o pedido, com passagens documentais como evidência. |
| Requisitos de execução impedindo a busca | Recuperar conhecimento pertinente e avaliar separadamente sua aplicabilidade. |
| Memória e verificações sobrepostas ao caminho antigo | Responsabilidades delimitadas e contexto inicial simples, rastreável. |
| Melhora em exemplos corrigidos apresentada como generalização | Separação entre desenvolvimento, validação reservada e teste final inédito. |

## Contrato de funcionamento

**Mensagem e contexto → interpretação → consultas → recuperação → análise das evidências → síntese ou esclarecimento → verificação → continuidade.**

| Etapa | Responsabilidade e resultado esperado |
|---|---|
| Interpretação | O modelo identifica objetivo, partes do pedido, fatos, restrições, mudanças e incertezas, rastreáveis às mensagens. |
| Consultas | O modelo traduz necessidades em buscas e pode decompor pedidos. A pergunta original permanece disponível para conferir desvios. |
| Recuperação | A aplicação combina busca semântica e textual. Retorna candidatos identificáveis e permite ampliar a passagem para seção, etapas, advertências, tabelas ou figuras. |
| Análise | O modelo distingue relevância, suficiência, aplicabilidade, conflito e lacuna. Uma boa pontuação de busca não autoriza uma orientação. |
| Síntese ou esclarecimento | O modelo explica, compara e organiza informações compatíveis. Pergunta somente o que possa mudar a orientação e ainda possa ser obtido. |
| Verificação | A aplicação confere integridade, referências e limites operacionais; o modelo auxilia a revisão de suporte e utilidade. Essa revisão não certifica segurança. |
| Continuidade | O contexto incorpora esclarecimentos e mudanças, preserva identidades e objetivos pendentes e permite consultar mensagens relevantes. |

Três compromissos complementam o fluxo:

1. Conferir cobertura do pedido: o que foi atendido, o que permanece pendente e por quê.
2. Incorporar cada esclarecimento relevante: o que foi acrescentado, corrigido, retirado ou tornou-se ambíguo.
3. Limitar buscas e revisões: uma busca complementar deve atender a uma necessidade identificável; ao atingir o limite, entregar a parte sustentada e explicar a pendência.

O número de tentativas ainda será definido por benefício e latência.

## Papel do modelo e da aplicação

O modelo interpreta linguagem e escreve a resposta. Regras determinísticas cuidam de integridade documental, permissões, referências, limites operacionais e cálculos explícitos. Não haverá uma árvore de respostas acionada por palavras nem obrigação de encerrar um pedido escolhendo uma única unidade documental.

Procedimentos, parâmetros e afirmações técnicas exigem suporte documental. Protocolos incompatíveis não podem ser fundidos silenciosamente. Relatos do usuário permanecem relatos; respostas anteriores do assistente não se tornam fatos sobre a pessoa.

Falta de informação da situação exige esclarecimento pertinente. Falta de evidência exige delimitar a lacuna. Informação ausente bloqueia apenas conclusões que dependam dela; não exige um formulário completo antes de qualquer ajuda.

## Biblioteca e contexto conversacional

Preservar originais e revisar a preparação do índice. Cada passagem deve manter título, instituição, edição, seção, localização e contexto de aplicação. Procedimentos precisam recuperar condições, etapas e advertências necessárias. Unidades editoriais podem organizar o acervo sem formar um catálogo fechado de respostas.

O contexto inicial usará histórico relevante e resumo curto, revisável e rastreável às mensagens. Deve preservar objetivos, recursos e condições relatados, itens ou fontes distintos, riscos, correções, incertezas, perguntas respondidas e orientações apresentadas.

Controle detalhado de estoque e ontologia extensa de capacidades ficam fora do núcleo inicial. Disponibilidade de um objeto não equivale à sua adequação técnica.

## Avaliação definida antes da implementação

O piloto terá oito famílias: obter/escolher água; tratar água; transportar/armazenar água; escolher alimentos; preparar alimentos com restrições; conservar alimentos; higiene/contaminação cruzada; priorizar necessidades combinadas.

| Conjunto | Quantidade | Uso |
|---|---:|---|
| Desenvolvimento D01–D24 | 24 conversas | Inspeção, ajustes e regressão. Exemplos antigos e variações próximas são conhecidos. |
| Validação reservada | 24 conversas, em duas rodadas de 12 | Avaliar versões congeladas; detalhes reservados até execução. |
| Teste final inédito | 24 conversas | Medição após congelamento; uma execução para aquela versão. |

Cada conjunto terá três conversas por família: pedido informado, esclarecimento decisivo e mudança/dificuldade. As conversas terão de uma a cinco mensagens do usuário. A separação deve considerar situações e trajetórias, não apenas trocar palavras.

Por conjunto, com sobreposição permitida, prever ao menos seis pedidos compostos, seis mudanças/correções, três ambiguidades, três informações impossíveis de obter, três lacunas de biblioteca e dois conflitos ou diferenças de escopo documental.

Cada caso precisa de objetivo, esclarecimentos disponíveis, evidências aceitáveis, condições essenciais, comportamentos exigidos, erros proibidos e encerramento definido. Não há uma redação única obrigatória. Depois de revelar e usar um caso para corrigir o sistema, ele passa a ser conhecido.

### Critérios de passagem do piloto

Os critérios de planejamento para validação reservada e teste final são simultâneos:

- Pelo menos **21/24** conversas com resultado adequado: resolvida ou limitação corretamente tratada.
- Pelo menos **85%** de resolução entre tarefas previamente classificadas como respondíveis.
- Pelo menos **2/3** adequadas em cada família.
- **Zero** erros críticos observados, parâmetros/procedimentos essenciais inventados e conversas estagnadas após esclarecimento suficiente.
- Perguntas redundantes ou impossíveis em no máximo **duas conversas**, sem impedir seu encaminhamento.
- Atendimento dos critérios de cada etapa.

Limitação corretamente tratada não equivale a tarefa resolvida e só conta quando corresponde à referência do caso.

Nas etapas, a meta inicial é **90%** para identificação de elementos decisivos, cobertura das necessidades de busca, recuperação suficiente nos casos respondíveis, julgamento de suficiência/aplicabilidade, suporte das afirmações técnicas relevantes e incorporação de mudanças. Todos os parâmetros procedimentais precisam de suporte; nenhuma condição essencial pode desaparecer. Sempre apresentar numeradores e denominadores aplicáveis.

O verificador terá diagnóstico separado de **16 respostas preparadas**: oito adequadas e oito com defeitos, incluindo quatro críticos. Deve detectar todos os críticos inseridos e bloquear indevidamente no máximo 10% das adequadas. Esse diagnóstico não entra no placar das conversas.

**Provisório:** 90 segundos por resposta em pelo menos 90% das respostas no computador-alvo. O limite precisa ser confirmado antes do congelamento.

### Método de avaliação

Avaliar componentes com entradas revisadas e também no fluxo real. Comparar geração com evidência suficiente fornecida diretamente e com evidência obtida pela busca para localizar a origem das falhas.

Congelar modelo, instruções, acervo, índice, contexto e limites de busca em cada rodada. Contar a primeira execução completa; diagnósticos e reexecuções técnicas justificadas ficam identificados separadamente. Usar julgamento humano como referência; casos críticos ou disputados exigem segunda revisão, permanecendo pendentes sem ela.

Medir fundamento, utilidade, cobertura, continuidade, bloqueio excessivo, erros críticos, buscas, esclarecimentos e latência. Comparar mudanças isoladas com uma referência simples de RAG antes de adicionar camadas. Ausência de erros observados em amostra pequena não comprova segurança geral.

## Cobertura documental já examinada

No planejamento dos **24 casos de desenvolvimento**, a revisão encontrou **10 com núcleo sustentado, 11 parciais e três lacunas centrais**. Isso descreve evidência disponível, não resultados de um sistema implementado. A conferência textual não substitui revisão visual dos parâmetros técnicos.

| Situação | Casos e assuntos |
|---|---|
| Núcleo sustentado | D01 escolha de água; D02 recipiente com histórico químico; D04 tratamento com recursos; D05 esclarecimento de consulta ampla; D07 armazenamento; D08 recipiente desconhecido; D12 latas distintas; D16 mantimentos; D18 comparação de condições de vegetais; D20 mãos sem torneira. |
| Parcial | D03 lacre rompido; D06 perda de combustível; D09 possível recontaminação; D10 escolha de alimentos; D11 lata sem identificação; D17 conservação de bananas; D19 utensílios após carne crua; D21 vegetais já expostos; D22 pouca água; D23 objetivos combinados; D24 planta desconhecida. |
| Lacuna central | D13 preparo de arroz; D14 arroz/feijão com poucos recursos; D15 cozimento interrompido. |

Prioridades de acervo: preparo básico e interrupção de cozimento; higienização operacional e destino de alimentos já expostos à carne crua; lacre comprometido e recontaminação de água; alimentos sem identificação e mofo fora do contexto de enchentes; conservação de frutas; escassez e limites de identificação de plantas.

Antes de incorporar conteúdo, corrigir IDs documentais reutilizados, distinguir original/recorte/adaptação, conferir visualmente OCR numérico, confrontar trechos antigos com referências atuais e preservar protocolos distintos. A lista de necessidades não significa que novas fontes já foram buscadas ou incorporadas.

## O que permanece aberto

Ainda não foram escolhidos os componentes definitivos, modelos, parâmetros de recuperação, orçamento de contexto, limite de tentativas e forma de persistência do resumo. Implementação, validação real da nova arquitetura e novas pesquisas documentais permanecem etapas futuras.

O próximo trabalho parte das lacunas identificadas e da preparação documental, preservando os casos reservados. Estes arquivos registram as decisões tomadas; sua criação não altera a aplicação instalada nem executa a segunda versão.
