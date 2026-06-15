from selenium.webdriver.support.ui           import WebDriverWait
from selenium.webdriver.support              import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions              import (
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)

import time

def safe_click(
    driver,
    element
):
    """
    Klickt ein Element robust:
    - scrollt es ins Viewport-Zentrum
    - setzt Fokus
    - normaler click()
    - Fallback: JS-click bei Intercept / Re-Render
    """
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center', inline:'center'});",
        element
    )
    try:
        element.click()
    except (ElementClickInterceptedException, StaleElementReferenceException):
        driver.execute_script("arguments[0].click();", element)

def double_click_element(
    driver,
    locator, 
    timeout=10):

    wait = WebDriverWait(driver, timeout)

    for _ in range(3):
        try:
            element = wait.until(EC.element_to_be_clickable(locator))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            ActionChains(driver).move_to_element(element).double_click(element).perform()
            return True
        except (StaleElementReferenceException, ElementClickInterceptedException):
            time.sleep(0.2)

    # letzter Versuch: JS click + ENTER (manche Grids reagieren darauf)
    element = wait.until(EC.presence_of_element_located(locator))
    driver.execute_script("arguments[0].click();", element)
    return True