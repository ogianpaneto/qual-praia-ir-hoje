import math, nltk
from dataclasses import dataclass


POSITIVE_LEXICON = {
    "agradavel": 1.0,
    "agradaveis": 1.0,
    "apropriado": 0.8,
    "barato": 0.5,
    "bares": 0.3,
    "aconchegante": 0.8,
    "bela": 1.0,
    "belas": 1.0,
    "boa": 0.8,
    "bom": 0.8,
    "bonita": 0.9,
    "bonito": 0.9,
    "calmas": 0.8,
    "calma": 0.8,
    "calmo": 0.8,
    "charme": 0.6,
    "ciclovia": 0.4,
    "conhecer": 0.4,
    "cristalino": 1.2,
    "cuidados": 0.5,
    "diferenciado": 0.8,
    "divertirem": 0.5,
    "excelentes": 1.4,
    "excelente": 1.4,
    "facil": 0.6,
    "familia": 0.4,
    "familiar": 0.5,
    "familias": 0.4,
    "feliz": 0.8,
    "gostosa": 0.8,
    "ideal": 0.6,
    "indico": 1.0,
    "incrivel": 1.2,
    "inesquecivel": 1.0,
    "interessante": 0.5,
    "interessantes": 0.5,
    "limpa": 1.2,
    "limpo": 1.2,
    "linda": 1.1,
    "lindo": 1.1,
    "maravilhoso": 1.3,
    "melhor": 1.0,
    "movimentada": 0.3,
    "opcao": 0.6,
    "opcoes": 0.5,
    "organizados": 0.8,
    "otima": 1.1,
    "otimas": 1.1,
    "otimo": 1.1,
    "paisagismo": 0.4,
    "paraiso": 1.1,
    "perfeita": 1.4,
    "perfeito": 1.4,
    "proximos": 0.4,
    "quiosques": 0.3,
    "rapido": 0.5,
    "raso": 0.5,
    "recomendo": 1.0,
    "relaxar": 0.7,
    "restaurantes": 0.3,
    "sombra": 0.3,
    "sofisticados": 0.4,
    "super": 0.3,
    "segura": 1.0,
    "seguro": 1.0,
    "seguranca": 0.8,
    "top": 1.1,
    "tranquila": 0.9,
    "tranquilas": 0.9,
    "tranquilo": 0.9,
    "tranquilos": 0.9,
    "voltaria": 0.8,
}

NEGATIVE_LEXICON = {
    "agitado": -0.6,
    "agitada": -0.6,
    "aglomeração": -0.8,
    "aglomeracao": -0.8,
    "barro": -0.9,
    "bravo": -0.7,
    "caco": -0.8,
    "cheiro": -0.8,
    "coliformes": -1.4,
    "contamina": -1.2,
    "contaminada": -1.2,
    "cuidado": -0.4,
    "desgastados": -0.6,
    "desrespeito": -1.0,
    "dificil": -0.7,
    "esburacados": -0.8,
    "esgoto": -1.5,
    "expostos": -0.6,
    "fecais": -1.4,
    "fiscalizar": -0.5,
    "fiscalizacao": -0.5,
    "fortes": -0.5,
    "furei": -1.0,
    "faltou": -0.4,
    "falta": -0.5,
    "faltando": -0.5,
    "gasolina": -1.0,
    "horrivel": -1.5,
    "impropria": -1.4,
    "improprio": -1.4,
    "inexistente": -0.9,
    "lixo": -1.3,
    "lotado": -0.9,
    "lotada": -0.9,
    "manutencao": -0.4,
    "marrom": -0.8,
    "mau": -1.0,
    "mato": -0.5,
    "oleo": -1.1,
    "pedras": -0.3,
    "pequena": -0.3,
    "prejudicada": -0.9,
    "pregos": -0.8,
    "problema": -0.7,
    "ruim": -1.0,
    "soltas": -0.5,
    "suja": -1.2,
    "sujeira": -1.2,
    "tampinhas": -0.3,
    "turva": -1.0,
    "vidro": -0.8,
}

NEGATIONS = {"nao", "nem", "nunca", "sem"}


@dataclass
class SentimentResult:
    polarity: float
    score_0_100: float
    token_count: int
    positive_hits: int
    negative_hits: int


def normalize_text(text: str) -> str:
    translation = str.maketrans(
        "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ",
        "aaaaeeioooucAAAAEEIOOOUC")
    return text.translate(translation).lower()


def tokenize(text: str) -> list[str]:
    return [token for token in nltk.wordpunct_tokenize(normalize_text(text)) if token.isalpha()]


def analyze_sentiment(text: str) -> SentimentResult:
    tokens = tokenize(text)
    raw_score = 0.0
    positive_hits = 0
    negative_hits = 0

    for i, token in enumerate(tokens):
        value = POSITIVE_LEXICON.get(token, NEGATIVE_LEXICON.get(token, 0.0))
        if value == 0.0:
            continue

        previous = set(tokens[max(0, i - 3) : i])
        if previous & NEGATIONS:
            value *= -0.75

        raw_score += value
        if value > 0:
            positive_hits += 1
        else:
            negative_hits += 1

    polarity = math.tanh(raw_score / max(1.0, len(tokens) ** 0.5))
    score_0_100 = round((polarity + 1) * 50, 2)

    return SentimentResult(
        polarity=round(polarity, 4),
        score_0_100=score_0_100,
        token_count=len(tokens),
        positive_hits=positive_hits,
        negative_hits=negative_hits,
    )
