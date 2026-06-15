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
    config: dict
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

    items_url = f"{graph_base}/sites/{site_id}/lists/{list_id}/items?$expand=fields"
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

def chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

def send_graph_batch(graph_base: str, headers: dict, batch_requests: list[dict]) -> dict:
    payload = {"requests": batch_requests}
    batch_url = f"{graph_base}/$batch"

    resp = requests.post(batch_url, headers=headers, json=payload)
    resp.raise_for_status()

    return resp.json()

def send_batched_requests(
    graph_base: str,
    headers: dict,
    requests_to_send: list[dict],
    max_retries: int = 6
):
    pending_requests = list(requests_to_send)

    for attempt in range(1, max_retries + 1):
        failed_requests = []
        retry_after_seconds = 0

        for batch_chunk in chunked(pending_requests, 20):
            batch_result = send_graph_batch(graph_base, headers, batch_chunk)

            requests_by_id = {
                request["id"]: request
                for request in batch_chunk
            }

            for response in batch_result.get("responses", []):
                status = response.get("status")
                request_id = response.get("id")

                if status is not None and 200 <= status < 300:
                    continue

                if status in {429, 502, 503, 504}:
                    failed_request = requests_by_id.get(request_id)
                    if failed_request:
                        failed_requests.append(failed_request)

                    retry_after = response.get("headers", {}).get("Retry-After")
                    if retry_after:
                        retry_after_seconds = max(
                            retry_after_seconds,
                            int(retry_after)
                        )
                    continue

                raise RuntimeError(
                    f"Graph batch subrequest failed: {response}"
                )

        if not failed_requests:
            return

        if attempt == max_retries:
            raise RuntimeError(
                f"Graph batch failed after {max_retries} retries. "
                f"Remaining failed requests: {len(failed_requests)}"
            )

        if retry_after_seconds <= 0:
            retry_after_seconds = min(30 * attempt, 180)

        print(
            f"[RETRY] {len(failed_requests)} request(s) failed transiently. "
            f"Retrying after {retry_after_seconds} seconds. "
            f"Attempt {attempt}/{max_retries}."
        )

        time.sleep(retry_after_seconds)
        pending_requests = failed_requests

def sync_endpoint(
    access_token: str,
    site_id:      str,
    source_items: list[dict],
    config:       dict
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

    sp_list = connect_sp_list(
        graph_base   = graph_base,
        site_id      = site_id,
        headers      = headers,
        source_items = source_items,
        config       = config
    )

    # ------------------------------------------------------------------------------
    # Sync: Compare / POST / PATCH
    # ------------------------------------------------------------------------------

    create_requests = []
    update_requests = []
    batch_request_id = 1

    for source_item in source_items:
        source_id_raw = source_item.get(source_id_field)
        if source_id_raw is None:
            continue

        source_id = str(source_id_raw)
        target = sp_list["index"].get(source_id)

        # ----------------------------------------------------------------------
        # A) Neues Item → POST
        # ----------------------------------------------------------------------

        if not target:
            new_post_request = create_post_request(
                site_id          = site_id,
                list_id          = sp_list["list_id"],
                source_id        = source_id,
                now_utc          = now_utc,
                source_item      = source_item,
                batch_request_id = batch_request_id,
                config           = config
            )
            create_requests.append(new_post_request)
            batch_request_id += 1
            continue

        # ----------------------------------------------------------------------
        # B) Bestehendes Item → Compare & PATCH
        # ----------------------------------------------------------------------

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

    all_batch_requests = create_requests + update_requests
    send_batched_requests(graph_base, headers, all_batch_requests)