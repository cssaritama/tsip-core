"""Market data connectors.

Each connector returns canonical bars (see :mod:`tsip.data.schema`) and never
fills, interpolates or invents observations. Network access is isolated in a
``getter`` argument so that parsing can be tested offline.
"""

from tsip.data.sources.base import SourceUnavailable

__all__ = ["SourceUnavailable"]
