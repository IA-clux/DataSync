import requests
import time
import sqlite3
from   typing import  Any, Dict, List, Optional
from   pathlib import Path

from Project.MS365.sp_client import sp_client

class ApiError(RuntimeError):
    pass

BASE_URL = "https://app.alldaycare.de"

CUSTOMERS_PATH             = "/bi/customers"
EMPLOYEES_PATH             = "/bi/employees"
CUSTOMEREMPLOYEELINKS_PATH = "/bi/customerEmployeeLinks"
INSURANCES_PATH            = "/bi/insurances"
RECEIPTS_PATH              = "/bi/receipts"

DEFAULT_PAGE_SIZE = 500

def fetch_page(
    controller: object,
    session: requests.Session,
    endpoint: str,
    token: str,
    page: int,
    page_size: int,
    timeout_s: int = 60,
) -> Dict[str, Any]:
    
    url = f"{BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    resp = session.get(
        url,
        headers=headers,
        params={"page": page, "pageSize": page_size},
        timeout=timeout_s,
    )

    # Token abgelaufen/ungültig (Doku: 401 bei missing/expired token)
    if resp.status_code == 401: 
        error_msg = "401 Unauthorized – Token fehlt oder ist abgelaufen. In Postman neu holen."
        # Response in Frontend anzeigen
        controller.gui.root.after(0, controller.gui.error_msg.config(state = "normal"))
        controller.gui.error_msg.insert("end", error_msg)
        controller.gui.error_msg.config(state = "disabled") 
        raise ApiError(error_msg)
    
    if resp.status_code == 403:
        error_msg = "403 Forbidden – keine Berechtigung oder falsche Audience/Permissions."
        # Response in Frontend anzeigen
        controller.gui.root.after(0, controller.gui.error_msg.config(state = "normal"))
        controller.gui.error_msg.insert("end", error_msg)
        controller.gui.error_msg.config(state = "disabled")        
        raise ApiError(error_msg)
    
    if resp.status_code >= 400:
        error_msg = f"HTTP {resp.status_code}: {resp.text[:500]}"
        # Response in Frontend anzeigen
        controller.gui.root.after(0, controller.gui.error_msg.config(state = "normal"))
        controller.gui.error_msg.insert("end", error_msg)
        controller.gui.error_msg.config(state = "disabled")
        raise ApiError(error_msg)

    return resp.json()

def fetch_all_items(
    controller: object,
    endpoint: str,
    token: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    sleep_s: float = 0.0
) -> List[Dict[str, Any]]:

    all_items: List[Dict[str, Any]] = []
    with requests.Session() as session:
        page = 1
        total_pages: Optional[int] = None

        while True:
            data = fetch_page(
                controller = controller,
                session    = session, 
                endpoint   = endpoint, 
                token      = token, 
                page       = page, 
                page_size  = page_size)

            items = data.get("items", [])
            all_items.extend(items)

            # API liefert Pagination-Metadaten (page, pageSize, totalPages, totalCount)
            total_pages = data.get("totalPages", total_pages)
            current_page = data.get("page", page)

            progress_in_pct = int((100 * current_page) / total_pages)
            if endpoint == CUSTOMERS_PATH:
                controller.gui.customer_progress.config(text = f"{progress_in_pct}%")
            elif endpoint == EMPLOYEES_PATH:
                controller.gui.employees_progress.config(text = f"{progress_in_pct}%")
            elif endpoint == INSURANCES_PATH:
                controller.gui.insurances_progress.config(text = f"{progress_in_pct}%")
            elif endpoint == RECEIPTS_PATH:
                controller.gui.receipts_progress.config(text = f"{progress_in_pct}%")

            print(f"Fetched page {current_page}/{total_pages} — items total: {len(all_items)}")

            if total_pages is not None and current_page >= total_pages:
                print()
                break

            page += 1
            if sleep_s > 0:
                time.sleep(sleep_s)

    return all_items

def fetch_all_entities(controller, token, page_size = DEFAULT_PAGE_SIZE):
    controller.gui.customer_progress_lbl.config(text="Lade Kundendaten:")
    customers = fetch_all_items(
        controller=controller,
        endpoint=CUSTOMERS_PATH,
        token=token,
        page_size=page_size
    )

    controller.gui.employees_progress_lbl.config(text="Lade Mitarbeiterdaten:")
    employees = fetch_all_items(
        controller=controller,
        endpoint=EMPLOYEES_PATH,
        token=token,
        page_size=page_size
    )

    customerEmployeeLinks = fetch_all_items(
        controller= controller,
        endpoint=CUSTOMEREMPLOYEELINKS_PATH,
        token=token,
        page_size=page_size
    )

    controller.gui.insurances_progress_lbl.config(text="Lade Kostenträgerdaten:")
    insurances = fetch_all_items(
        controller=controller,
        endpoint=INSURANCES_PATH,
        token=token,
        page_size=page_size
    )

    controller.gui.receipts_progress_lbl.config(text="Lade Belegdaten:")
    receipts = fetch_all_items(
        controller=controller,
        endpoint=RECEIPTS_PATH,
        token=token,
        page_size=page_size
    )

    return {
        "customers":             customers,
        "employees":             employees,
        "customerEmployeeLinks": customerEmployeeLinks,
        "insurances":            insurances,
        "receipts":              receipts,
    }

import sqlite3
from pathlib import Path


LOCAL_COLUMNS = {
    "customers": {
        "EBAvailable": "INTEGER DEFAULT 0",
        "VHPCurrentYear": "INTEGER DEFAULT 0",
    },
    "insurances": {
        "InvoiceRecipient": "TEXT DEFAULT '----'",
        "ShippingMethod": "TEXT DEFAULT '----'",
    },
}


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def detect_type(items, key):
    for item in items:
        if key in item and item[key] is not None:
            value = item[key]

            # bool muss vor int geprüft werden, weil bool eine int-Unterklasse ist
            if isinstance(value, bool):
                return "INTEGER"
            if isinstance(value, int):
                return "INTEGER"
            if isinstance(value, float):
                return "REAL"

            return "TEXT"

    return "TEXT"


def get_existing_columns(cur, table_name: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({quote_identifier(table_name)})")
    return {row[1] for row in cur.fetchall()}


def table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
        AND name = ?
        """,
        (table_name,),
    )
    return cur.fetchone() is not None


def ensure_table_schema(
    cur,
    table_name: str,
    items: list[dict],
    primary_key: str,
):
    if not items:
        return

    api_keys: list[str] = []

    for item in items:
        for key in item.keys():
            if key not in api_keys:
                api_keys.append(key)

    if primary_key not in api_keys:
        raise RuntimeError(
            f"Primary Key '{primary_key}' fehlt in Items von Tabelle '{table_name}'."
        )

    local_columns = LOCAL_COLUMNS.get(table_name, {})

    if not table_exists(cur, table_name):
        column_defs = []

        for key in api_keys:
            sql_type = detect_type(items, key)

            if key == primary_key:
                column_defs.append(
                    f"{quote_identifier(key)} {sql_type} PRIMARY KEY"
                )
            else:
                column_defs.append(
                    f"{quote_identifier(key)} {sql_type}"
                )

        for key, definition in local_columns.items():
            column_defs.append(
                f"{quote_identifier(key)} {definition}"
            )

        create_sql = (
            f"CREATE TABLE {quote_identifier(table_name)} "
            f"({', '.join(column_defs)})"
        )

        cur.execute(create_sql)
        return

    existing_columns = get_existing_columns(cur, table_name)

    for key in api_keys:
        if key not in existing_columns:
            sql_type = detect_type(items, key)
            cur.execute(
                f"""
                ALTER TABLE {quote_identifier(table_name)}
                ADD COLUMN {quote_identifier(key)} {sql_type}
                """
            )

    existing_columns = get_existing_columns(cur, table_name)

    for key, definition in local_columns.items():
        if key not in existing_columns:
            cur.execute(
                f"""
                ALTER TABLE {quote_identifier(table_name)}
                ADD COLUMN {quote_identifier(key)} {definition}
                """
            )


def sync_table(
    cur,
    table_name: str,
    items: list[dict],
    primary_key: str,
):
    """
    Synchronisiert API-Daten in eine SQLite-Tabelle.

    Verhalten:
    - Tabelle wird NICHT gelöscht
    - fehlende API-Spalten werden ergänzt
    - lokale Zusatzspalten bleiben erhalten
    - bestehende Datensätze werden anhand Primary Key aktualisiert
    - nicht mehr gelieferte Datensätze werden NICHT gelöscht
    """

    if not items:
        return

    ensure_table_schema(
        cur=cur,
        table_name=table_name,
        items=items,
        primary_key=primary_key,
    )

    api_keys: list[str] = []

    for item in items:
        for key in item.keys():
            if key not in api_keys:
                api_keys.append(key)

    quoted_table = quote_identifier(table_name)
    quoted_columns = [quote_identifier(key) for key in api_keys]

    insert_columns_sql = ", ".join(quoted_columns)
    placeholders_sql = ", ".join("?" for _ in api_keys)

    update_columns = [
        key for key in api_keys
        if key != primary_key
    ]

    update_sql = ", ".join(
        f"{quote_identifier(key)} = excluded.{quote_identifier(key)}"
        for key in update_columns
    )

    if update_sql:
        sql = f"""
            INSERT INTO {quoted_table} ({insert_columns_sql})
            VALUES ({placeholders_sql})
            ON CONFLICT({quote_identifier(primary_key)})
            DO UPDATE SET {update_sql}
        """
    else:
        sql = f"""
            INSERT INTO {quoted_table} ({insert_columns_sql})
            VALUES ({placeholders_sql})
            ON CONFLICT({quote_identifier(primary_key)})
            DO NOTHING
        """

    for item in items:
        row = []

        for key in api_keys:
            value = item.get(key, None)

            if isinstance(value, bool):
                value = 1 if value else 0

            row.append(value)

        cur.execute(sql, row)


def push_to_sqlite(database_path: Path, data: dict):
    db_path = Path(database_path) / "alldaycare.db"

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        sync_table(cur, "customers", data["customers"], "CustomerId")
        sync_table(cur, "employees", data["employees"], "EmployeeId")
        sync_table(cur, "insurances", data["insurances"], "FundId")
        sync_table(cur, "receipts", data["receipts"], "ReceiptId")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def push_to_sharepoint(data: dict):

    for endpoint in ("customers", "insurances", "employees", "receipts"):
        if endpoint not in data:
            print(f"[WARNING] Missing data for endpoint '{endpoint}'")
            continue

        sp_client.upsert_endpoint(data[endpoint], endpoint=endpoint)

