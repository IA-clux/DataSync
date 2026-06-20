from dotenv import load_dotenv
from pathlib import Path
import os
import sys

from Project.MS365.graph_get_access_token import graph_get_access_token
from Project.MS365.graph_sync_endpoint    import sync_endpoint

from typing import Literal


def _load_env():
    # In der gepackten Exe (PyInstaller onefile) liegt die .env im
    # entpackten Bundle-Verzeichnis (sys._MEIPASS); im Entwicklungsbetrieb
    # wird sie wie gewohnt aus dem Arbeitsverzeichnis geladen.
    if hasattr(sys, "_MEIPASS"):
        bundled_env = Path(sys._MEIPASS) / ".env"
        if bundled_env.exists():
            load_dotenv(bundled_env)
            return
    load_dotenv()


_load_env()

class sp_client:

    TENANT_ID     = os.getenv("AZURE_TENANT_ID")
    CLIENT_ID     = os.getenv("AZURE_CLIENT_ID")
    CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")

    SITE_ID = "ihrealltagsbegleiter.sharepoint.com,02199624-2845-496e-9293-80837aa8f58b,7c69ab61-4721-4ceb-ad35-3f0d6e41bf1b"

    CONFIGS = {
        "customers": {
            "list_name": "Customers",
            "source_id_field": "CustomerId",
            "target_id_column": "Source_CustomerId",
            "title_value": "Customer",
            "fallback_column": {
                "type": "text",
                "multi": True
            },
            "columns": {
                "Source_CustomerId": {"type": "text", "multi": False, "max_length": 255},
                "LastSyncAt": {"type": "text", "multi": False, "max_length": 255},
                "Source_Number": {"type": "text", "multi": False, "max_length": 255},
                "Source_Salutation": {"type": "text", "multi": False, "max_length": 255},
                "Source_Title": {"type": "text", "multi": False, "max_length": 255},
                "Source_FirstName": {"type": "text", "multi": False, "max_length": 255},
                "Source_LastName": {"type": "text", "multi": False, "max_length": 255},
                "Source_EntryDate": {"type": "text", "multi": False, "max_length": 255},
                "Source_DateOfBirth": {"type": "text", "multi": False, "max_length": 255},
                "Source_CareLevel": {"type": "text", "multi": False, "max_length": 255},
                "Source_InsuranceNumber": {"type": "text", "multi": False, "max_length": 255},
                "Source_Remarks": {"type": "text", "multi": True},
                "Source_FundId": {"type": "text", "multi": False, "max_length": 255},
                "Source_Address": {"type": "text", "multi": False, "max_length": 255},
                "Source_AdditionalAddress": {"type": "text", "multi": False, "max_length": 255},
                "Source_City": {"type": "text", "multi": False, "max_length": 255},
                "Source_ZipCode": {"type": "text", "multi": False, "max_length": 255},
                "Source_ServiceType": {"type": "text", "multi": False, "max_length": 255},
                "Source_CreatedAt": {"type": "text", "multi": False, "max_length": 255},
                "Source_Commitment": {"type": "text", "multi": True},
            }
        },
        "employees": {
            "list_name": "Employees",
            "source_id_field": "EmployeeId",
            "target_id_column": "Source_EmployeeId",
            "title_value": "Employee",
            "fallback_column": {
                "type": "text",
                "multi": True
            },
            "columns": {
                "Source_EmployeeId": {"type": "text", "multi": False, "max_length": 255},
                "LastSyncAt": {"type": "text", "multi": False, "max_length": 255},
                "Source_Number": {"type": "text", "multi": False, "max_length": 255},
                "Source_Salutation": {"type": "text", "multi": False, "max_length": 255},
                "Source_Title": {"type": "text", "multi": False, "max_length": 255},
                "Source_FirstName": {"type": "text", "multi": False, "max_length": 255},
                "Source_LastName": {"type": "text", "multi": False, "max_length": 255},
                "Source_EntryDate": {"type": "text", "multi": False, "max_length": 255},
                "Source_DateOfBirth": {"type": "text", "multi": False, "max_length": 255},
                "Source_Address": {"type": "text", "multi": False, "max_length": 255},
                "Source_AdditionalAddress": {"type": "text", "multi": False, "max_length": 255},
                "Source_City": {"type": "text", "multi": False, "max_length": 255},
                "Source_ZipCode": {"type": "text", "multi": False, "max_length": 255},
                "Source_CreatedAt": {"type": "text", "multi": False, "max_length": 255},
            }
        },
        "insurances": {
            "list_name": "Insurances",
            "source_id_field": "FundId",
            "target_id_column": "Source_FundId",
            "title_value": "Insurance",
            "fallback_column": {
                "type": "text",
                "multi": True
            },
            "columns": {
                "Source_FundId": {"type": "text", "multi": False, "max_length": 255},
                "LastSyncAt": {"type": "text", "multi": False, "max_length": 255},
                "Source_FullName": {"type": "text", "multi": False, "max_length": 255},
                "Source_Type": {"type": "text", "multi": False, "max_length": 255},
                "Source_Address": {"type": "text", "multi": False, "max_length": 255},
                "Source_AdditionalAddress": {"type": "text", "multi": False, "max_length": 255},
                "Source_City": {"type": "text", "multi": False, "max_length": 255},
                "Source_ZipCode": {"type": "text", "multi": False, "max_length": 255},
                "Source_CreatedAt": {"type": "text", "multi": False, "max_length": 255},
            }
        },
        "receipts": {
            "list_name": "Receipts",
            "source_id_field": "ReceiptId",
            "target_id_column": "Source_ReceiptId",
            "title_value": "Receipt",
            "fallback_column": {
                "type": "text",
                "multi": True
            },
            "columns": {
                "Source_ReceiptId": {"type": "text", "multi": False, "max_length": 255},
                "LastSyncAt": {"type": "text", "multi": False, "max_length": 255},
                "Source_CustomerId": {"type": "text", "multi": False, "max_length": 255},
                "Source_EmployeeId": {"type": "text", "multi": False, "max_length": 255},
                "Source_ItemId": {"type": "text", "multi": False, "max_length": 255},
                "Source_ItemVersion": {"type": "text", "multi": False, "max_length": 255},
                "Source_ItemCustomerId": {"type": "text", "multi": False, "max_length": 255},
                "Source_BeginAt": {"type": "text", "multi": False, "max_length": 255},
                "Source_Quantity": {"type": "text", "multi": False, "max_length": 255},
                "Source_CreatedAt": {"type": "text", "multi": False, "max_length": 255},
                "Source_ExtendedTime": {"type": "text", "multi": False, "max_length": 255},
            }
        },
        "customer_employee_links": {
            "list_name": "CustomerEmployeeLinks",
            "source_id_field": "LinkId",
            "target_id_column": "Source_LinkId",
            "title_value": "CustomerEmployeeLink",
            "fallback_column": {
                "type": "text",
                "multi": True
            },
            "columns": {
                "Source_LinkId": {"type": "text", "multi": False, "max_length": 255},
                "LastSyncAt": {"type": "text", "multi": False, "max_length": 255},
                "Source_CustomerId": {"type": "text", "multi": False, "max_length": 255},
                "Source_EmployeeId": {"type": "text", "multi": False, "max_length": 255},
                "Source_IsPrimary": {"type": "text", "multi": False, "max_length": 255},
                "Source_IsRepresentative": {"type": "text", "multi": False, "max_length": 255},
                "Source_CreatedAt": {"type": "text", "multi": False, "max_length": 255},
            }
        },
    }

# ---------------------------------------------------------------------------------------------

    @staticmethod
    def upsert_endpoint(
        source_data: list[dict],
        endpoint: Literal["customers", "insurances", "employees", "receipts", "customer_employee_links"],
        progress_callback=None):

        selected_config = sp_client.CONFIGS[endpoint]

        access_token = graph_get_access_token(
            tenant_id     = sp_client.TENANT_ID,
            client_id     = sp_client.CLIENT_ID,
            client_secret = sp_client.CLIENT_SECRET
        )

        sync_endpoint(
            access_token     = access_token,
            site_id          = sp_client.SITE_ID,
            source_items     = source_data,
            config           = selected_config,
            progress_callback = progress_callback
        )