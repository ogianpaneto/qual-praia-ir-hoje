import json
import re
import uuid
import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from slugify import slugify
from dataclasses import dataclass
from enum import Enum


VITORIA_URL = "https://www.vitoria.es.gov.br/balneabilidade.php"
VILA_VELHA_URL = "https://novo.vilavelha.es.gov.br/dashboards/balneabilidade.aspx"
SERRA_URL = "https://www.serra.es.gov.br/site/pagina/balneabilidade-das-praias"


class PointStatus(Enum):
    PROPER = "Próprio"
    IMPROPER = "Impróprio"
    INTERDITED = "Interditado"


@dataclass(frozen=True)
class BathingPoint:
    beach_id: str
    point_id: str
    status: PointStatus
    location: str
    source: str


def scrape_vitoria_balneability() -> list[BathingPoint]:
    points: list[BathingPoint] = []
    html = requests.get(VITORIA_URL).content
    soup = BeautifulSoup(html, "html.parser")
    
    ul = soup.find("ul", class_="balneabilidade")
    
    for li in ul.find_all("li"):
        info_div = li.find("div", class_="info")
        info_text = info_div.text.strip()
        location = info_div.find("small").text.strip()
        
        beach_id = _extract_beach_id(info_text)
        point_id = li.get("id", "").strip()
        status_text = li.find("div", class_="status").text.strip()
        status = PointStatus(status_text)
        
        points.append(
            BathingPoint(
                beach_id=beach_id,
                point_id=point_id,
                status=status,
                location=location,
                source=VITORIA_URL,
            )
        )

    return points


def scrape_serra_balneability() -> list[BathingPoint]:
    points: list[BathingPoint] = []

    html = requests.get(SERRA_URL).content
    soup = BeautifulSoup(html, "html.parser")

    iframe = soup.find("iframe")
    if not iframe:
        return points

    iframe_url = iframe.get("src", "").strip()
    iframe_html = requests.get(iframe_url).text

    match = re.search(r'var _pageData = "(.*)";</script>', iframe_html)

    if not match:
        return points

    page_data = match.group(1)

    # O conteúdo vem com aspas escapadas: \"
    # Sem isso, o regex não encontra nada.
    page_data = page_data.replace('\\"', '"')

    pattern = re.compile(
        r'"([A-F0-9]{16})",\[\[\[[-0-9.,]+\]\]\].*?'
        r'\[\["nome",\["(Ponto\s+\d+\s*-\s*[^"]+)"\],1\],'
        r'\["descrição",\["([^"]+)"\],1\]\]',
        re.DOTALL,
    )

    matches = pattern.findall(page_data)

    for point_id, location, description in matches:
        location = location.replace("\xa0", " ")
        location = re.sub(r"\s+", " ", location).strip()

        first_description_line = description.split("\\n")[0]

        if "IMPR" in first_description_line.upper():
            status = PointStatus.IMPROPER
        else:
            status = PointStatus.PROPER

        beach_name = re.sub(
            r"^Ponto\s+\d+\s*-\s*",
            "",
            location,
        ).strip()

        beach_name = beach_name.replace("\xa0", " ")
        beach_name = re.sub(r"\s+", " ", beach_name).strip()

        # Remove algarismo romano no final:
        # "Nova Almeida I" -> "Nova Almeida"
        # "Manguinhos III" -> "Manguinhos"
        beach_name = re.sub(
            r"\s+(I|II|III|IV|V|VI|VII|VIII|IX|X)\b.*$",
            "",
            beach_name,
        ).strip()

        beach_id = slugify(beach_name)

        points.append(
            BathingPoint(
                beach_id=beach_id,
                point_id=point_id,
                status=status,
                location=location,
                source=SERRA_URL,
            )
        )

    return points



def scrape_vila_velha_balneability() -> list[BathingPoint]:
    points: list[BathingPoint] = []
    html = requests.get(VILA_VELHA_URL).content
    soup = BeautifulSoup(html, "html.parser")
    
    iframe = soup.find("iframe", title=re.compile("balneabilidade", re.IGNORECASE))
    iframe_url = iframe.get("src", "").strip()
    iframe_html = requests.get(iframe_url).text

    resource_key, api_base = _extract_powerbi_resource_key_and_api(iframe_html)

    model_id, visual_query = _fetch_powerbi_models_and_query(resource_key, api_base)

    querydata = _fetch_powerbi_querydata(resource_key, api_base, model_id, visual_query)

    rows = _extract_rows_from_querydata(querydata)

    for row in rows:
        status = _map_status(row.get("classification", ""))
        if status is None:
            continue
        
        beach_name = row.get("location", "").strip()
        beach_name = beach_name.replace("\xa0", " ")
        beach_name = re.sub(r"\s+", " ", beach_name).strip()
        beach_name = re.sub(
            r"\s+(I|II|III|IV|V|VI|VII|VIII|IX|X)\b.*$",
            "",
            beach_name,
        ).strip()

        points.append(
            BathingPoint(
                beach_id=slugify(beach_name),
                point_id=row.get("point", ""),
                status=status,
                location=row.get("location", ""),
                source=VILA_VELHA_URL,
            )
        )

    return points


def _extract_beach_id(info_text: str) -> str:
    first_line = info_text.splitlines()[0]
    beach_name = first_line.split(" / ")[0].strip() if " / " in first_line else first_line.strip()
    return slugify(beach_name)


def _extract_powerbi_resource_key_and_api(iframe_html: str) -> tuple[str | None, str | None]:
    unescaped = iframe_html.replace('\\"', '"')
    resource_match = re.search(r'"k":"([^"]+)"', unescaped)
    cluster_match = re.search(r"resolvedClusterUri\s*=\s*'([^']+)'", iframe_html)
    resource_key = resource_match.group(1) if resource_match else None
    if not resource_key or not cluster_match:
        return None, None

    cluster_uri = cluster_match.group(1)
    api_base = _powerbi_api_base(cluster_uri)
    return resource_key, api_base


def _powerbi_api_base(cluster_uri: str) -> str:
    host = cluster_uri.replace("https://", "").replace("http://", "").strip("/")
    host = host.replace("-redirect", "").replace("global-", "")
    if "-api" not in host:
        host = host.replace(".analysis.windows.net", "-api.analysis.windows.net")
    return f"https://{host}"


def _fetch_powerbi_models_and_query(resource_key: str, api_base: str) -> tuple[str | None, dict | None]:
    url = f"{api_base}/public/reports/{resource_key}/modelsAndExploration?preferReadOnlySession=true"
    response = requests.get(url, headers=_powerbi_headers(resource_key))
    if not response.ok:
        return None, None
    data = response.json()

    model_id = None
    if isinstance(data.get("models"), list) and data["models"]:
        model_id = data["models"][0].get("id")

    visual_query = _find_table_visual_query(data)
    return model_id, visual_query


def _find_table_visual_query(data: dict) -> dict | None:
    exploration = data.get("exploration") or {}
    sections = exploration.get("sections") or []
    for section in sections:
        query = _find_table_query_in_visuals(section.get("visualContainers", []))
        if query:
            return query

    config_raw = exploration.get("config")
    if config_raw:
        try:
            config = json.loads(config_raw)
        except json.JSONDecodeError:
            return None
        for bookmark in config.get("bookmarks", []):
            state = bookmark.get("explorationState", {})
            sections_state = (state.get("sections") or {}).values()
            for section_state in sections_state:
                visuals = (section_state.get("visualContainers") or {}).values()
                query = _find_table_query_in_visuals(visuals)
                if query:
                    return query
    return None


def _find_table_query_in_visuals(visuals) -> dict | None:
    for visual in visuals:
        config_raw = visual.get("config") if isinstance(visual, dict) else None
        if not config_raw:
            continue
        try:
            config = json.loads(config_raw)
        except json.JSONDecodeError:
            continue
        single = config.get("singleVisual", {})
        if single.get("visualType") not in {"table", "tableEx"}:
            continue
        query_raw = visual.get("query") if isinstance(visual, dict) else None
        query = _parse_visual_query(query_raw) if query_raw else None
        if query and "Commands" in query:
            return query
        query = single.get("prototypeQuery") or single.get("query")
        if query:
            return query
    return None


def _parse_visual_query(query_raw: str | dict | None) -> dict | None:
    if query_raw is None:
        return None
    if isinstance(query_raw, dict):
        return query_raw
    if isinstance(query_raw, str):
        try:
            return json.loads(query_raw)
        except json.JSONDecodeError:
            return None
    return None


def _fetch_powerbi_querydata(resource_key: str, api_base: str, model_id: str, query: dict) -> dict | None:
    url = f"{api_base}/public/reports/querydata"
    query_payload = query
    if "Commands" not in query_payload:
        query_payload = {"Commands": [{"SemanticQueryDataShapeCommand": {"Query": query_payload}}]}
    payload = {
        "version": "1.0.0",
        "queries": [{"Query": query_payload, "QueryId": "0"}],
        "cancelQueries": [],
        "modelId": model_id,
    }
    response = requests.post(url, headers=_powerbi_headers(resource_key), json=payload)
    if not response.ok:
        return None
    data = response.json()
    return data


def _extract_rows_from_querydata(data: dict) -> list[dict[str, str]]:
    results = data.get("results") or []
    if not results:
        return []
    result = results[0].get("result") or {}
    ds = result.get("data", {}).get("dsr", {}).get("DS", [])
    if not ds:
        return []
    rows: list[dict[str, str]] = []
    for dataset in ds:
        value_dicts = dataset.get("ValueDicts") or {}
        for ph in dataset.get("PH", []):
            for dm_key, dm_val in ph.items():
                if not dm_key.startswith("DM") or not isinstance(dm_val, list):
                    continue
                schema = _extract_schema(dm_val)
                if not schema:
                    continue
                previous_decoded: list[str] | None = None
                for row in dm_val:
                    if not isinstance(row, dict):
                        continue
                    cells = row.get("C") or []
                    if not cells:
                        continue
                    decoded = _decode_cells(schema, cells, value_dicts, row.get("R"), previous_decoded)
                    if len(decoded) < 5:
                        continue
                    previous_decoded = decoded
                    classification = decoded[2]
                    rows.append(
                        {
                            "location": decoded[0],
                            "point": decoded[1],
                            "classification": classification,
                            "long": decoded[3],
                            "lat": decoded[4],
                        }
                    )
    return rows


def _cell_value(cells: list, index: int) -> str:
    if index >= len(cells):
        return ""
    value = cells[index].get("V") if isinstance(cells[index], dict) else None
    return str(value) if value is not None else ""


def _extract_schema(dm_rows: list[dict]) -> list[dict]:
    for row in dm_rows:
        if isinstance(row, dict) and "S" in row:
            return row.get("S") or []
    return []


def _decode_cells(
    schema: list[dict],
    cells: list,
    value_dicts: dict,
    repeat_mask: int | None = None,
    previous_decoded: list[str] | None = None,
) -> list[str]:
    if not schema:
        return []

    decoded: list[str] = []
    cell_index = 0
    for index in range(len(schema)):
        schema_item = schema[index] if index < len(schema) else {}
        if repeat_mask and repeat_mask & (1 << index):
            decoded.append(previous_decoded[index] if previous_decoded and index < len(previous_decoded) else "")
            continue
        if cell_index >= len(cells):
            decoded.append("")
            continue
        cell = cells[cell_index]
        cell_index += 1
        dict_name = schema_item.get("DN")
        if dict_name and dict_name in value_dicts:
            values = value_dicts.get(dict_name, [])
            try:
                decoded.append(str(values[int(cell)]))
            except (ValueError, IndexError, TypeError):
                decoded.append("")
        else:
            decoded.append(str(cell))
    return decoded


def _powerbi_headers(resource_key: str) -> dict:
    request_id = str(uuid.uuid4())
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "ActivityId": request_id,
        "RequestId": request_id,
        "X-PowerBI-ResourceKey": resource_key,
    }


def _map_status(value: str) -> PointStatus | None:
    normalized = slugify(value).lower()
    if normalized == "propria":
        return PointStatus.PROPER
    if normalized in {"impropria", "sist-impropria"}:
        return PointStatus.IMPROPER
    if normalized in {"interditada", "interditado"}:
        return PointStatus.INTERDITED
    return None


def _write_points(file_path: Path, points: list[BathingPoint]) -> None:
    data = [
        {
            "beach_id": point.beach_id,
            "point_id": point.point_id,
            "status": point.status.value,
            "location": point.location,
            "source": point.source,
        }
        for point in points
    ]
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def scrape_bathing_points() -> list[BathingPoint]:
    """Aggregate bathing points from supported municipalities."""
    points: list[BathingPoint] = []
    try:
        points.extend(scrape_vitoria_balneability())
    except Exception:
        pass
    try:
        points.extend(scrape_vila_velha_balneability())
    except Exception:
        pass
    try:
        points.extend(scrape_serra_balneability())
    except Exception:
        pass
    return points


def write_bathing_points_csv(points: list[BathingPoint], file_path: Path) -> None:
    """Write bathing points to a CSV file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["beach_id", "point_id", "status", "location", "source"])
        for p in points:
            writer.writerow([p.beach_id, p.point_id, p.status.value, p.location, p.source])


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2] / "data"
    _write_points(base_dir / "vitoria_balneability_points.json", scrape_vitoria_balneability())
    _write_points(base_dir / "vila_velha_balneability_points.json", scrape_vila_velha_balneability())
    _write_points(base_dir / "serra_balneability_points.json", scrape_serra_balneability())
