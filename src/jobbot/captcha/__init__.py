"""Pluggable captcha solvers."""
from .base import CaptchaSolver, NullSolver
from .twocaptcha import TwoCaptchaSolver

from ..config import Config, Secrets


def get_captcha_solver(secrets: Secrets, config: Config) -> CaptchaSolver:
    if not secrets.captcha_api_key:
        return NullSolver()
    if secrets.captcha_provider == "twocaptcha":
        return TwoCaptchaSolver(secrets.captcha_api_key, config.captcha.timeout_s)
    return NullSolver()


__all__ = ["CaptchaSolver", "NullSolver", "TwoCaptchaSolver", "get_captcha_solver"]
