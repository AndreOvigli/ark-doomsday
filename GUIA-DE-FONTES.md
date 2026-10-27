# Guia de fontes: como montar o seu acervo

O ARK é o motor; o acervo é seu. O repositório não traz os documentos que usamos, porque eles pertencem às instituições que os publicaram. Este guia diz como escolher fontes confiáveis para montar a sua biblioteca, seja você escolhendo à mão, seja um modelo buscando para você.

Se quiser um ponto de partida, [acervo/fontes.json](acervo/fontes.json) lista as 24 fontes do nosso acervo, com licença. O script [acervo/baixar_acervo.py](acervo/baixar_acervo.py) tenta baixá-las e [acervo/recortes/](acervo/recortes/) traz os recortes traduzidos de fontes de domínio público ou CC BY. Isso aproxima o nosso acervo, mas não o reproduz byte a byte.

## Os seis critérios

Uma fonte entra quando passa em todos.

1. **Autoridade no tema.** Órgão de saúde pública, vigilância sanitária, defesa civil, saneamento ou extensão rural/universitária. Para dose, tempo e conservação, só fonte oficial. Blog, fórum, vídeo e manual "de sobrevivencialista" ficam de fora, mesmo quando parecem certos.
2. **Licença que permite o uso.** Confira a página de direitos do site ou o expediente do PDF e anote o link. Domínio público e Creative Commons são os mais simples. "Está na internet" não quer dizer "pode usar", e "é do governo" não quer dizer domínio público fora dos EUA.
3. **Escrita para a situação certa.** Prefira texto para casa e pessoa comum, no formato "situação, passos, quando não fazer". Material para cozinha industrial, norma técnica ou política pública confunde o modelo: ele transforma uma regra de restaurante em ordem para a sua despensa.
4. **Diz quando não fazer.** As respostas mais perigosas que medimos vieram de fontes que ensinam a tratar sem dizer quando a água ou o alimento não tem salvação. Uma fonte que traz contraindicação vale mais do que três que só dão a receita.
5. **Data e edição conhecidas.** Registre ano, edição e data do download. Desconfie de documento sem data, e não confunda a data da página com a data do conteúdo.
6. **Cabe na arca.** Anote páginas e MB. O ARK é para rodar em máquina modesta; um PDF de 300 páginas com 20 úteis custa disco, memória e ruído na busca.

## Como registrar cada fonte

Uma linha por documento, no formato do `fontes.json`:

| Campo | Exemplo |
| --- | --- |
| id | ARK-025 |
| titulo | Título como aparece no documento |
| instituicao | Quem publicou |
| url | Endereço oficial do original |
| tipo | pdf ou html |
| licenca | Texto curto da licença |
| licenca_fonte | Link da política de direitos ou "expediente do PDF" |
| sha256_captura | Hash do arquivo no dia do download |

Fontes em outro idioma entram como recortes traduzidos, com a linha `FONTE:` no topo indicando a instituição e o documento original. Indique sempre que é tradução.

## Instruções para um modelo que busca fontes

Se você usa um assistente para montar o acervo, entregue a ele este bloco:

> Busque documentos oficiais sobre [tema] para uma pessoa em casa, sem água encanada, luz ou gás. Aceite apenas órgãos públicos de saúde, vigilância sanitária, defesa civil, saneamento ou extensão universitária. Para cada documento, traga: título, instituição, URL do original, data ou edição, licença com o link da política de direitos do site, número de páginas e se ele diz quando NÃO fazer. Não invente URL nem licença: se não encontrou, escreva "não encontrado". Descarte blogs, fóruns, vídeos e lojas. Prefira texto no formato situação, passos e contraindicações.

Confira à mão o que o modelo trouxer: abra cada URL e a página de licença antes de incluir.

## Como medir com o seu acervo

Os nossos números (no README) valem para o nosso acervo. Com outro acervo, os números mudam, e tudo bem: o que importa num PR é o antes e o depois **no mesmo acervo**.

Os casos de avaliação em `v2/eval/` citam trechos do nosso acervo. Com o seu, use as mensagens dos casos como perguntas e refaça a coluna de trechos aceitos com as suas passagens.
