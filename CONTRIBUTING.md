# Como contribuir com o ARK

Obrigado por querer ajudar. O ARK responde perguntas em que um erro pode fazer alguém beber água contaminada ou comer comida estragada, então o processo é mais rígido do que num projeto comum. Ele cabe em três regras.

## 1. Corrigimos categorias de erro, nunca frases

A v1 do ARK morreu de remendo: cada pergunta que falhava ganhava um sinônimo, uma palavra-chave ou uma regra própria, e o sistema virou uma colcha que acertava os testes e errava o próximo usuário. Por isso, toda correção precisa:

- **Não citar o objeto ou o caso.** "Água de piscina não se trata" é regra de caso. "Quando a fonte disser que algo não se trata, a resposta não pode ensinar a tratar" é regra de categoria.
- **Corrigir vários erros de uma vez.** Se só um caso melhora, provavelmente é remendo.
- **Ser medida em perguntas inéditas.** O ganho nos casos que você já conhecia não prova nada.

PR que conserta só uma pergunta específica não entra, mesmo que funcione.

## 2. Todo PR mostra o antes e o depois

Se o PR mexe na busca, no prompt, no modelo ou na resposta, a descrição traz:

| | Antes | Depois |
| --- | --- | --- |
| Busca: recall@8 nos casos de dev | | |
| Resposta: cobertura nos casos de dev | | |
| Respostas perigosas | | |
| Tempo por resposta | | |
| Pico de memória (VRAM e RAM) | | |
| Disco adicional | | |

Meça o antes e o depois **no mesmo acervo** e diga qual usou. Não precisa ser o nosso: o que vale é a diferença.

Respostas perigosas é a trava: um PR que aumenta esse número é rejeitado, mesmo que melhore todo o resto. O mesmo vale para quem estoura o orçamento de memória e tempo sem uma boa razão. O ARK é uma arca, e o objetivo é caber em máquina cada vez mais fraca.

Comandos para medir estão no [README](README.md#como-medir).

## 3. Fonte nova só com licença conferida

Os critérios estão no [GUIA-DE-FONTES.md](GUIA-DE-FONTES.md). Para sugerir um documento à lista de referência, abra uma issue com o modelo "Nova fonte". Ela precisa de:

- Instituição oficial ou de autoridade reconhecida no tema (saúde pública, vigilância sanitária, defesa civil, extensão universitária).
- Licença que permita redistribuir, ou ao menos baixar e usar localmente, registrada com o link da política do site.
- Qual dúvida real ela resolve e que o acervo atual não resolve.

Não mande o arquivo da fonte no PR. Entra só a linha em `acervo/fontes.json`, com URL, licença e SHA256.

## O que mais ajuda agora

- **Achar respostas perigosas.** Use o ARK com dúvidas reais e abra uma issue "Resposta perigosa" quando a resposta contrariar a fonte.
- **Escrever casos de avaliação.** Dúvidas do dia a dia sem água, luz ou gás, escritas sem olhar o acervo.
- **Rodar em hardware mais fraco.** Modelos menores, quantização, CPU, celular. Sempre com a tabela de antes e depois.
- Issues marcadas como `bom primeiro PR`.

## O que fica fora do piloto

O piloto é água e alimentação no dia a dia, num colapso da infraestrutura urbana. Catástrofes naturais (enchente, terremoto) ficam para um segundo nível. Propostas nesses temas são bem-vindas como discussão, não como PR no acervo do piloto.

## Detalhes práticos

- Idioma: português do Brasil em código, comentários, docs e respostas.
- Commits pequenos e com mensagem que diga o porquê.
- Ao contribuir, você concorda que seu código entra sob a licença MIT e seus textos e casos de avaliação sob CC BY 4.0.
- O conjunto de teste final não está no repositório, de propósito. Se estivesse, deixaria de ser inédito.
