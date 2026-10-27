# Segurança e limites do ARK

## O ARK pode errar, e às vezes erra de forma perigosa

O ARK é um experimento. Ele usa um modelo de linguagem pequeno, que roda no seu computador, para resumir documentos oficiais. Modelos assim às vezes ignoram o que a fonte diz.

O erro perigoso mais comum que medimos tem um padrão: **a fonte diz para não usar, e o modelo diz para tratar e usar.** Na validação com 20 dúvidas reais, isso aconteceu 3 vezes (água de piscina, água com cheiro estranho, água guardada que estragou). Uma foi corrigida; as outras seguem abertas. O placar atualizado está no [README](README.md#onde-está-hoje).

## Como usar com segurança

- **Confira sempre a fonte citada.** O ARK mostra o documento e a página. Se a resposta disser algo que a fonte não diz, confie na fonte.
- **Na dúvida, não consuma.** Se a resposta e a fonte não deixam claro que é seguro, trate como não seguro.
- **Doses e tempos vêm da fonte, não do modelo.** O ARK tenta remover números sem fonte, mas confira gotas por litro, minutos de fervura e horas de conservação no documento.
- **Ele não substitui ninguém.** Em emergência, siga a Defesa Civil (199), o SAMU (192), os bombeiros (193) e o serviço de saúde local.
- **Não use para saúde de pessoas.** Sintomas, medicamentos e primeiros socorros estão fora do escopo do piloto.

## O que o ARK não faz

- Não garante que a informação está atualizada: o acervo é uma foto das fontes no dia do download.
- Não cobre desastres naturais, só o dia a dia sem água, luz ou gás.
- Não conhece sua situação além do que você conta.

## Como reportar uma resposta perigosa

Abra uma issue com o modelo **"Resposta perigosa"**, com a pergunta, a resposta completa, a fonte citada e o que a fonte dizia de verdade. Esse é o tipo de contribuição mais valioso para o projeto.

Se encontrar uma falha de segurança no software (não na resposta), por exemplo algo que exponha o computador na rede, não abra issue pública: use o [aviso privado de vulnerabilidade](https://github.com/AndreOvigli/ark-doomsday/security/advisories/new) do GitHub.

## Sem garantia

O ARK é distribuído "como está", sem garantia de nenhum tipo, conforme a [licença](LICENSE). Quem usa assume a responsabilidade pelas decisões que toma.
