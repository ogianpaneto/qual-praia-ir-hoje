import argparse, json
from pathlib import Path

from praias_ai.balneability_scraper import scrape_bathing_points, write_bathing_points_csv
from praias_ai.index_model import build_index, load_csv, load_json
from praias_ai.weather import fetch_open_meteo_weather, load_local_weather, write_weather_snapshot_csv


ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera o índice dinâmico de qualidade das praias.")
    parser.add_argument("--output", default=DATA_DIR / "latest_index.json", type=Path)
    parser.add_argument("--skip-bathing-scrape", action="store_true", help="Usa data/bathing_points.csv sem atualizar por scraping.")
    return parser.parse_args()


def generate_index(output: Path | None = None, skip_bathing_scrape: bool = False) -> dict:
    output = output or DATA_DIR / "latest_index.json"
    beaches = load_json(DATA_DIR / "beaches.json")
    posts = load_csv(DATA_DIR / "reviews.csv")

    if not skip_bathing_scrape:
        scraped_bathing = scrape_bathing_points()
        if scraped_bathing:
            write_bathing_points_csv(scraped_bathing, DATA_DIR / "bathing_points.csv")
            print("Balneabilidade atualizada.")
        else:
            print("Scraping de balneabilidade não retornou pontos; usando CSV local.")

    bathing = load_csv(DATA_DIR / "bathing_points.csv")

    try:
        weather = fetch_open_meteo_weather(beaches)
        write_weather_snapshot_csv(weather, DATA_DIR / "weather_snapshot.csv")
        print("Clima ao vivo consultado com sucesso.")
    except Exception as exc:
        print(f"Falha ao consultar clima ao vivo ({exc}); usando snapshot local.")
        weather = load_local_weather(DATA_DIR / "weather_snapshot.csv")

    result = build_index(beaches, posts, weather, bathing)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Índice gerado em {output}")
    return result


def main():
    args = parse_args()
    generate_index(args.output, args.skip_bathing_scrape)

if __name__ == "__main__":
    main()
