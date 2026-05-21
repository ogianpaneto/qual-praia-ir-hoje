# Metodologia do índice

O índice varia de 0 a 100 e combina dois grupos de sinais, com desconto por balneabilidade apenas quando todos os pontos oficiais da praia estiverem impróprios ou interditados:

| Grupo | Peso | Origem no MVP |
| --- | ---: | --- |
| Percepção pública | 40% | Reviews/postagens + nota de 1 a 5 |
| Clima | 60% | Temperatura, chuva, vento, UV e ondas |

## NLP com NLTK

O arquivo `src/praias_ai/sentiment.py` usa `nltk.wordpunct_tokenize` para tokenizar textos em português. Em seguida, aplica um léxico inicial PT-BR com termos positivos e negativos relacionados a praias, como `limpa`, `cristalino`, `lixo`, `turva` e `lotada`.

## Fórmula

```text
indice_base = percepcao_publica * 0.40 + clima * 0.60
indice = indice_base - desconto_balneabilidade
```

A percepção pública mistura sentimento textual e nota numérica:

```text
percepcao_publica = sentimento * 0.65 + nota_media_normalizada * 0.35
```

Pontos impróprios ou interditados são sempre sinalizados na página. Eles só descontam do índice quando não houver nenhum ponto próprio:

```text
desconto_balneabilidade = 15, se todos os pontos forem impróprios/interditados
desconto_balneabilidade = 0, caso contrário
```
