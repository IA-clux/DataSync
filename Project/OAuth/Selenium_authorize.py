from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from Project.OAuth.Selenium_handlers import safe_click


# ---------------------------------------------------------
# Driver Setup
# ---------------------------------------------------------

def setup_driver(debug_mode: bool = False) -> webdriver.Edge:
    options = Options()

    # Performance & Stabilität
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    # Anti-Bot-Minimierung (bewusst pragmatisch)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if not debug_mode:
        options.add_argument("--headless=new")

    return webdriver.Edge(
        options=options,
        service=Service()
    )


# ---------------------------------------------------------
# OAuth Selenium Login
# ---------------------------------------------------------

def selenium_oauth_login(
    log,
    auth_url: str,
    username: str,
    password: str,
    organisation: str,
    debug_mode: bool = False,
    timeout: int = 120
) -> None:
    """
    Führt einen vollständigen OAuth Login via Selenium aus
    und wartet darauf, dass der Redirect zu localhost erfolgt.

    Erfolg = Redirect ausgelöst
    Token-Verarbeitung erfolgt NICHT hier!
    """

    driver = setup_driver(debug_mode=debug_mode)
    wait = WebDriverWait(driver, timeout)

    try:
        # -------------------------------------------------
        # 1) OAuth Authorize URL öffnen
        # -------------------------------------------------
        driver.get(auth_url)

        # -------------------------------------------------
        # 2) Organisation eingeben
        # -------------------------------------------------
        org_field = wait.until(
            EC.visibility_of_element_located((By.ID, "organizationName"))
        )

        org_submit = wait.until(
            EC.element_to_be_clickable((By.NAME, "action"))
        )

        org_field.send_keys(organisation)
        safe_click(driver, org_submit)

        # Race: Fehler ODER Username-Feld
        org_error = (By.ID, "error-element-organizationName")
        username_field = (By.ID, "username")

        result = wait.until(
            EC.any_of(
                EC.visibility_of_element_located(org_error),
                EC.visibility_of_element_located(username_field)
            )
        )

        if result.get_attribute("id") == "error-element-organizationName":
            log_normal(log, f"Falscher Organisationsname: {organisation}")
            raise RuntimeError("Organisation ungültig")

        # -------------------------------------------------
        # 3) Benutzername & Passwort
        # -------------------------------------------------
        username_input = wait.until(
            EC.visibility_of_element_located(username_field)
        )
        password_input = driver.find_element(By.ID, "password")
        login_button = driver.find_element(By.NAME, "action")

        username_input.send_keys(username)
        password_input.send_keys(password)
        safe_click(driver, login_button)

        # -------------------------------------------------
        # 4) OAuth-Erfolg = Redirect auf localhost
        # -------------------------------------------------
        wait.until(EC.url_contains("localhost:58271"))

        # ✅ Bis hierher: Login erfolgreich & Redirect ausgelöst

    except TimeoutException:
        log_normal(log, "Timeout beim OAuth-Login")
        raise

    except Exception as e:
        log_normal(log, f"Selenium OAuth Fehler: {e}")
        raise

    finally:
        # -------------------------------------------------
        # 5) Browser immer sauber schließen
        # -------------------------------------------------
        driver.quit()


# ---------------------------------------------------------
# Logging Helper
# ---------------------------------------------------------

def log_normal(log_widget, message: str) -> None:
    log_widget.config(state="normal")
    log_widget.insert("end", message + "\n")
    log_widget.config(state="disabled")