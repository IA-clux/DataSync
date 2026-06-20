import requests
import time
from   datetime import datetime, timezone

# ------------------------------------------------------------------------------------
# KONFIGURATION (alles Externes wird injiziert)
# ------------------------------------------------------------------------------------
def normalize_value(value):
    if value is None:
        return ""
    return str(value)

def debug_field_lengths(fields: dict, source_id: str, config: dict):
    too_long = []

    for field_name, field_value in fields.items():
        column_config = config["columns"].get(
            field_name,
            config.get("fallback_column", {"type": "text", "multi": True})
        )

        if column_config.get("multi", False):
            continue

        max_length = column_config.get("max_length")

        if max_length is None:
            continue

        if isinstance(field_value, str):
            length = len(field_value)
            if length > max_length:
                too_long.append((field_name, length, field_value[:300]))

    if too_long:
        print(f"[LENGTH WARNING] source_id={source_id}")
        for field_name, length, preview in too_long:
            print(f"  - {field_name}: {length} chars")
            print(f"    preview: {preview}")
            print()

def build_column_payload(column_name: str, column_config: dict) -> dict:
    column_type = column_config.get("type")

    if column_type == "text":
        return {
            "name": column_name,
            "text": {
                "allowMultipleLines": column_config.get("multi", False)
            }
        }

    raise ValueError(
        f"Unsupported column type '{column_type}' for column '{column_name}'."
    )

def connect_sp_list(
    graph_base: str,
    site_id: str,
    headers: dict,
    source_items: list[dict],
    config: dict,
    id_only: bool = False
):
    # ------------------------------------------------------------------------------
    # 1. Liste laden oder erstellen
    # ------------------------------------------------------------------------------

    lists_url = f"{graph_base}/sites/{site_id}/lists"
    resp = requests.get(lists_url, headers=headers)
    resp.raise_for_status()

    lists = resp.json()["value"]
    target_list = next(
        (l for l in lists if l["displayName"] == config["list_name"]),
        None
    )

    if not target_list:
        payload = {
            "displayName": config["list_name"],
            "list": {"template": "genericList"}
        }
        resp = requests.post(lists_url, headers=headers, json=payload)
        resp.raise_for_status()
        target_list = resp.json()

    list_id = target_list["id"]

    # ------------------------------------------------------------------------------
    # 2. Schema laden und fehlende Columns anlegen
    # ------------------------------------------------------------------------------

    columns_url = f"{graph_base}/sites/{site_id}/lists/{list_id}/columns"
    resp = requests.get(columns_url, headers=headers)
    resp.raise_for_status()

    existing_columns = {col["name"] for col in resp.json()["value"]}

    required_columns = {
        config["target_id_column"],
        "LastSyncAt"
    }

    source_fields = set()
    for item in source_items:
        for key in item.keys():
            if key != config["source_id_field"]:
                source_fields.add(f"Source_{key}")

    all_source_columns = required_columns | source_fields

    for column_name in all_source_columns:
        if column_name in existing_columns:
            continue

        column_config = config["columns"].get(
            column_name,
            config["fallback_column"]
        )

        column_payload = build_column_payload(column_name, column_config)

        requests.post(
            columns_url,
            headers=headers,
            json=column_payload
        ).raise_for_status()

    # ------------------------------------------------------------------------------
    # 3. Bestehende Items laden
    # ------------------------------------------------------------------------------

    # Für unveränderliche Endpunkte genügt die ID-Spalte für das Delta — das
    # reduziert die zurückgelesene Nutzlast erheblich.
    if id_only:
        expand = f"fields($select={config['target_id_column']})"
    else:
        expand = "fields"

    items_url = f"{graph_base}/sites/{site_id}/lists/{list_id}/items?$expand={expand}"
    sp_items = fetch_all_list_items(items_url, headers)

    sp_index = {}
    for item in sp_items:
        fields = item.get("fields", {})
        source_id_value = fields.get(config["target_id_column"])
        if source_id_value:
            sp_index[str(source_id_value)] = {
                "item_id": item["id"],
                "fields": fields
            }

    return {
        "list_id": list_id,
        "index": sp_index
    }

def fetch_all_list_items(url: str, headers: dict) -> list[dict]:
    items = []

    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return items

def create_post_request(
    site_id: str,
    list_id: str,
    source_id: str,
    now_utc: str,
    source_item: dict,
    batch_request_id: int,
    config: dict
):
    fields = {
        "Title": config["title_value"],
        config["target_id_column"]: source_id,
        "LastSyncAt": now_utc
    }

    for key, value in source_item.items():
        if key == config["source_id_field"]:
            continue

        fields[f"Source_{key}"] = normalize_value(value)

    payload = {"fields": fields}
    debug_field_lengths(fields, source_id, config)

    return {
        "id": str(batch_request_id),
        "method": "POST",
        "url": f"/sites/{site_id}/lists/{list_id}/items",
        "headers": {
            "Content-Type": "application/json"
        },
        "body": payload
    }

def create_patch_request(
    site_id: str,
    list_id: str,
    item_id: str,
    now_utc: str,
    source_item: dict,
    sp_fields: dict,
    batch_request_id: int,
    config: dict
):
    delta = {}

    for key, value in source_item.items():
        if key == config["source_id_field"]:
            continue

        col_name = f"Source_{key}"
        normalized_value = normalize_value(value)

        if sp_fields.get(col_name) != normalized_value:
            delta[col_name] = normalized_value

    if not delta:
        return None

    delta["LastSyncAt"] = now_utc

    return {
        "id": str(batch_request_id),
        "method": "PATCH",
        "url": f"/sites/{site_id}/lists/{list_id}/items/{item_id}/fields",
        "headers": {
            "Content-Type": "application/json"
        },
        "body": delta
    }

def create_delete_request(
    site_id: str,
    list_id: str,
    item_id: str,
    batch_request_id: int
):
    return {
        "id": str(batch_request_id),
        "method": "DELETE",
        "url": f"/sites/{site_id}/lists/{list_id}/items/{item_id}",
    }

def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

def send_graph_batch(graph_base: str, headers: dict, batch_requests: list[dict]) -> dict:
    payload = {"requests": batch_requests}
    batch_url = f"{graph_base}/$batch"

    resp = requests.post(batch_url, headers=headers, json=payload)

    # Der $batch-Wrapper selbst kann unter Last gedrosselt werden (429/503).
    # In diesem Fall NICHT hart abbrechen, sondern als transienten Fehler
    # signalisieren, damit der gesamte Chunk via Retry-After erneut läuft.
    if resp.status_code in {429, 503}:
        retry_after = resp.headers.get("Retry-After")
        return {
            "_batch_throttled": True,
            "retry_after": int(retry_after) if retry_after else 0,
        }

    # Access Token während eines langen Pushs abgelaufen → signalisieren, damit der
    # Aufrufer den Token erneuern und den Chunk erneut senden kann (statt Abbruch).
    if resp.status_code == 401:
        return {"_unauthorized": True}

    resp.raise_for_status()

    return resp.json()

# Feste Pause zwischen aufeinanderfolgenden $batch-Aufrufen, um die Aufrufrate zu
# senken (Microsoft-Best-Practice „Reduce the frequency of calls"). Bei Drosselung
# wird NICHT adaptiv verlangsamt — stattdessen wird gemäß Microsoft-Guidance exakt
# der vom Server gelieferte Retry-After-Wert abgewartet (siehe send_batched_requests).
SLEEP_BETWEEN_BATCHES = 1.0

# Schutz gegen Endlosschleife, falls Token-Erneuerung dauerhaft 401 liefert.
MAX_AUTH_REFRESHES = 10


def sleep_with_status(seconds: int, status_callback=None,
                      reason: str = "SharePoint drosselt – Pause"):
    """Blockierende Wartezeit mit Sekunden-Countdown im Status (statt scheinbarem
    Einfrieren)."""
    seconds = int(seconds)
    if status_callback is None:
        time.sleep(seconds)
        return
    for remaining in range(seconds, 0, -1):
        status_callback(f"{reason}: noch {remaining}s …")
        time.sleep(1)


def send_batched_requests(
    graph_base: str,
    headers: dict,
    requests_to_send: list[dict],
    max_no_progress_rounds: int = 6,
    progress_callback=None,
    status_callback=None,
    sleep_between_batches: float = SLEEP_BETWEEN_BATCHES,
    token_provider=None,
):
    pending = list(requests_to_send)
    auth_refreshes = 0

    total = len(requests_to_send)

    # Fortschritt zählt endgültig abgeschlossene Subrequests (2xx ODER dauerhaft
    # fehlgeschlagen) über ALLE Runden hinweg. Transient gedrosselte (429/503)
    # zählen erst, wenn ihr Retry erfolgreich war — sonst stünde der Balken bei
    # 100 %, obwohl noch Retries laufen.
    completed = 0

    # Dauerhaft fehlgeschlagene Einzel-Requests (z. B. 400/409/404): werden
    # gesammelt und übersprungen, statt den gesamten Push abzubrechen.
    permanent_failures = []

    # Statt einer festen Versuchszahl: solange Fortschritt entsteht, weitermachen.
    # Nur bei mehreren Runden komplett ohne Fortschritt wird abgebrochen — so
    # laufen auch sehr große Mengen trotz wiederholter Drosselung durch.
    no_progress_rounds = 0

    while pending:
        failed = []
        retry_after_seconds = 0
        completed_before_round = completed
        n = len(pending)
        idx = 0

        while idx < n:
            batch_chunk = pending[idx: idx + 20]
            batch_result = send_graph_batch(graph_base, headers, batch_chunk)

            # Der gesamte $batch-Wrapper wurde gedrosselt → sofort aufhören zu
            # senden; diesen und alle noch nicht gesendeten Chunks zurückstellen.
            if batch_result.get("_batch_throttled"):
                failed.extend(pending[idx:])
                retry_after_seconds = max(
                    retry_after_seconds,
                    batch_result.get("retry_after", 0)
                )
                break

            # Token während des Pushs abgelaufen → erneuern und denselben Chunk
            # erneut senden (idx bleibt stehen), statt abzubrechen.
            if batch_result.get("_unauthorized"):
                if token_provider is None or auth_refreshes >= MAX_AUTH_REFRESHES:
                    raise RuntimeError(
                        "Graph $batch: 401 Unauthorized – Access Token konnte nicht "
                        "erneuert werden."
                    )
                headers["Authorization"] = f"Bearer {token_provider()}"
                auth_refreshes += 1
                print(f"[AUTH] Access Token nach 401 erneuert (#{auth_refreshes}).")
                continue

            requests_by_id = {
                request["id"]: request
                for request in batch_chunk
            }

            chunk_throttled = False
            auth_refresh_pending = False

            for response in batch_result.get("responses", []):
                status = response.get("status")
                request_id = response.get("id")

                if status is not None and 200 <= status < 300:
                    completed += 1
                    continue

                if status in {429, 502, 503, 504}:
                    failed_request = requests_by_id.get(request_id)
                    if failed_request:
                        failed.append(failed_request)

                    retry_after = response.get("headers", {}).get("Retry-After")
                    if retry_after:
                        retry_after_seconds = max(
                            retry_after_seconds,
                            int(retry_after)
                        )
                    chunk_throttled = True
                    continue

                # Token-Ablauf auf Subrequest-Ebene → zurückstellen und Token nach
                # diesem Chunk erneuern; Retry erfolgt in der nächsten Runde.
                if status == 401:
                    failed_request = requests_by_id.get(request_id)
                    if failed_request:
                        failed.append(failed_request)
                    auth_refresh_pending = True
                    continue

                # Nicht-transienter Fehler eines einzelnen Subrequests:
                # protokollieren und überspringen (kein Abbruch des Gesamt-Pushes).
                # Zählt als abgeschlossen, da kein Retry mehr folgt.
                permanent_failures.append(response)
                completed += 1
                print(
                    f"[SKIP] Subrequest dauerhaft fehlgeschlagen "
                    f"(HTTP {status}): {response.get('body')}"
                )

            if progress_callback is not None and total > 0:
                progress_callback(completed, total)

            # Token nach erkanntem Subrequest-401 erneuern, damit Folge-Chunks und
            # der Retry der zurückgestellten Requests den frischen Token nutzen.
            if auth_refresh_pending and token_provider is not None and auth_refreshes < MAX_AUTH_REFRESHES:
                headers["Authorization"] = f"Bearer {token_provider()}"
                auth_refreshes += 1
                print(f"[AUTH] Access Token nach 401 (Subrequest) erneuert (#{auth_refreshes}).")

            # Drosselung in diesem Chunk → restliche, noch nicht gesendete Chunks
            # zurückstellen und Runde beenden (nicht weiter ins Limit feuern).
            if chunk_throttled:
                failed.extend(pending[idx + 20:])
                break

            idx += 20

            if sleep_between_batches > 0:
                time.sleep(sleep_between_batches)

        if not failed:
            if permanent_failures:
                print(
                    f"[WARNING] {len(permanent_failures)} Subrequest(s) dauerhaft "
                    f"fehlgeschlagen und übersprungen."
                )
            return

        # Wurde in dieser Runde überhaupt etwas abgeschlossen?
        if completed > completed_before_round:
            no_progress_rounds = 0
        else:
            no_progress_rounds += 1
            if no_progress_rounds >= max_no_progress_rounds:
                raise RuntimeError(
                    f"Graph batch: {no_progress_rounds} Runden ohne Fortschritt. "
                    f"Verbleibend: {len(failed)} Request(s), erledigt {completed}/{total}."
                )

        # Kein Retry-After vom Server (laut Doku selten bei SharePoint) → gemäß
        # Microsoft-Guidance exponentielles Backoff als Fallback.
        if retry_after_seconds <= 0:
            retry_after_seconds = min(30 * (no_progress_rounds + 1), 180)

        print(
            f"[RETRY] {len(failed)} Request(s) zurückgestellt. "
            f"Backoff {retry_after_seconds}s (Retry-After). Erledigt {completed}/{total}. "
            f"Runden ohne Fortschritt: {no_progress_rounds}."
        )

        sleep_with_status(retry_after_seconds, status_callback)
        if status_callback is not None:
            status_callback("Übertragung wird fortgesetzt…")
        pending = failed

def sync_endpoint(
    access_token: str,
    site_id:      str,
    source_items: list[dict],
    config:       dict,
    progress_callback=None,
    status_callback=None,
    token_provider=None
):
    
    # ------------------------------------------------------------------------------
    # Prepare Variables
    # ------------------------------------------------------------------------------

    source_id_field  = config["source_id_field"]

    graph_base = "https://graph.microsoft.com/v1.0"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    now_utc = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------------------
    # Connect / Initialize Sharepoint List
    # ------------------------------------------------------------------------------

    is_immutable = bool(config.get("immutable"))

    sp_list = connect_sp_list(
        graph_base   = graph_base,
        site_id      = site_id,
        headers      = headers,
        source_items = source_items,
        config       = config,
        id_only      = is_immutable
    )

    if is_immutable:
        all_batch_requests = build_immutable_requests(
            site_id, sp_list, source_items, source_id_field, now_utc, config
        )
    else:
        all_batch_requests = build_upsert_requests(
            site_id, sp_list, source_items, source_id_field, now_utc, config
        )

    send_batched_requests(
        graph_base,
        headers,
        all_batch_requests,
        progress_callback=progress_callback,
        status_callback=status_callback,
        token_provider=token_provider
    )


def build_upsert_requests(site_id, sp_list, source_items, source_id_field, now_utc, config):
    """Standardmodus: neue Items POST, geänderte Items PATCH (Feldvergleich),
    keine Löschungen."""
    create_requests = []
    update_requests = []
    batch_request_id = 1

    for source_item in source_items:
        source_id_raw = source_item.get(source_id_field)
        if source_id_raw is None:
            continue

        source_id = str(source_id_raw)
        target = sp_list["index"].get(source_id)

        # A) Neues Item → POST
        if not target:
            create_requests.append(create_post_request(
                site_id          = site_id,
                list_id          = sp_list["list_id"],
                source_id        = source_id,
                now_utc          = now_utc,
                source_item      = source_item,
                batch_request_id = batch_request_id,
                config           = config
            ))
            batch_request_id += 1
            continue

        # B) Bestehendes Item → Compare & PATCH
        new_patch_request = create_patch_request(
            site_id          = site_id,
            list_id          = sp_list["list_id"],
            item_id          = target["item_id"],
            now_utc          = now_utc,
            source_item      = source_item,
            sp_fields        = target["fields"],
            batch_request_id = batch_request_id,
            config           = config
        )

        if new_patch_request:
            update_requests.append(new_patch_request)
            batch_request_id += 1

    return create_requests + update_requests


def build_immutable_requests(site_id, sp_list, source_items, source_id_field, now_utc, config):
    """Modus für unveränderliche Endpunkte (z. B. Belege): reines ID-Delta —
    neue IDs einfügen (ohne Feldvergleich), in der Quelle entfernte IDs löschen,
    vorhandene unverändert lassen."""
    sp_index = sp_list["index"]
    create_requests = []
    delete_requests = []
    batch_request_id = 1

    source_ids = set()

    for source_item in source_items:
        source_id_raw = source_item.get(source_id_field)
        if source_id_raw is None:
            continue

        source_id = str(source_id_raw)
        source_ids.add(source_id)

        # Nur neue IDs einfügen; vorhandene bleiben unangetastet (immutable).
        if source_id not in sp_index:
            create_requests.append(create_post_request(
                site_id          = site_id,
                list_id          = sp_list["list_id"],
                source_id        = source_id,
                now_utc          = now_utc,
                source_item      = source_item,
                batch_request_id = batch_request_id,
                config           = config
            ))
            batch_request_id += 1

    # Löschungen: IDs in der Liste, die die Quelle nicht mehr liefert.
    # Sicherheitsgurt: nur löschen, wenn die Quelle überhaupt Daten geliefert hat
    # (verhindert das Leerräumen der Liste bei leerem/fehlgeschlagenem Pull).
    if source_ids:
        for sp_id, target in sp_index.items():
            if sp_id not in source_ids:
                delete_requests.append(create_delete_request(
                    site_id          = site_id,
                    list_id          = sp_list["list_id"],
                    item_id          = target["item_id"],
                    batch_request_id = batch_request_id
                ))
                batch_request_id += 1

    print(
        f"[IMMUTABLE] {config['list_name']}: {len(create_requests)} neu, "
        f"{len(delete_requests)} gelöscht, {len(sp_index)} im Bestand."
    )

    return create_requests + delete_requests