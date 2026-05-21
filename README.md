# Qual praia ir hoje?

MVP de IA/ML e NLP para combinar percepção pública, balneabilidade por pontos e clima em um índice dinâmico de qualidade de praias de Vitória, Vila Velha e Serra.

## O que o projeto faz

- Lê reviews/postagens de exemplo em `data/reviews.csv`.
- Usa NLTK para tokenizar texto em português e calcular sentimento com um léxico inicial customizável.
- Atualiza `data/bathing_points.csv` por web scraping quando fontes oficiais publicam pontos em HTML.
- Combina sentimento, avaliações numéricas e clima em um índice de 0 a 100, sinalizando pontos impróprios/interditados e descontando 15 pontos somente quando todos os pontos da praia estiverem ruins.
- Gera `data/latest_index.json`.
- Exibe o resultado em uma página web simples em `web/index.html`.

## Como rodar

1. Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

2. Gere o índice:

```powershell
python src/generate_index.py
```

3. Na pasta do projeto, rode:

```powershell
python -m http.server 8000
```

Depois acesse `http://localhost:8000/web/`.


## Aviso

Este é um projeto de estudo de tecnologia, feito para experimentar scraping, NLP, dados climáticos e visualização web. Ele não deve ser usado para tomada de decisões reais. Consulte sempre fontes oficiais e atualizadas.
