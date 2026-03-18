from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.webdriver import WebDriver as FirefoxDriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.safari.webdriver import WebDriver as SafariDriver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrowserConfig:
    headless: bool = True
    implicit_wait_seconds: float = 5.0
    user_agent: str | None = None


def _create_safari(config: BrowserConfig) -> WebDriver:
    options = SafariOptions()

    if config.user_agent:
        logger.info("Ignoring custom user agent for Safari; not supported by safaridriver.")

    if config.headless:
        logger.info("Safari headless mode is not supported; launching standard Safari automation session.")

    driver = SafariDriver(options=options)
    driver.implicitly_wait(config.implicit_wait_seconds)
    return driver


def _create_firefox(config: BrowserConfig) -> WebDriver:
    options = FirefoxOptions()
    if config.headless:
        options.add_argument("-headless")
    if config.user_agent:
        options.set_preference("general.useragent.override", config.user_agent)
    driver = FirefoxDriver(options=options)
    driver.implicitly_wait(config.implicit_wait_seconds)
    return driver


def create_webdriver(config: BrowserConfig | None = None) -> WebDriver:
    cfg = config or BrowserConfig()
    safari_ok = os.uname().sysname == "Darwin" and cfg.user_agent is None
    last_error: Exception | None = None

    if safari_ok:
        try:
            logger.info("Attempting to launch Safari WebDriver (primary).")
            return _create_safari(cfg)
        except WebDriverException as exc:
            last_error = exc
            logger.warning("Safari WebDriver unavailable, falling back to Firefox: %s", exc, exc_info=exc)

    try:
        logger.info("Attempting to launch Firefox WebDriver (fallback).")
        return _create_firefox(cfg)
    except WebDriverException as exc:
        if last_error:
            logger.error("Firefox WebDriver failed after Safari failure: %s", exc, exc_info=exc)
            raise RuntimeError("Neither Safari nor Firefox WebDriver could be started.") from exc
        logger.error("Firefox WebDriver failed: %s", exc, exc_info=exc)
        raise
