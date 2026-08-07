"""Job-alert email ingestion: the sanctioned path for boards that forbid crawling."""
from .runner import scan_alerts, scan_alerts_standalone

__all__ = ["scan_alerts", "scan_alerts_standalone"]
