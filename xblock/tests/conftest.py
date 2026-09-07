"""Minimal Django settings for this package's tests, mirroring ``pxc``'s own minimal-settings
approach for its XBlock (``pxc/src/pxc/xblock/settings.py``): just enough to import and exercise
``sparkth_pxc.xblock`` without a full Open edX runtime.
"""

import django
from django.conf import settings

settings.configure(
    SPARKTH_PXC_BASE_URL="https://sparkth.example",
    SPARKTH_PXC_LAUNCH_SECRET="s",
    SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS=300,
)
django.setup()
