"""Top-level package for ak_tools."""

#import parallel processor as pp

from ak_tools.parallel_processing import parallel_processor as pp
from ak_tools.sync_alert import download_alerts

__all__ = ["pp", "download_alerts"] #for __all__ import *
__version__ = "0.1.0"
