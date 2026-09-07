import os
from pathlib import Path

# Where the per-activity-type SQLite state files and the activities' file storage live.
# One file per activity type holds every course and every learner for that type (D1).
PXC_DATA_DIR = Path(os.getenv("PXC_DATA_DIR", "./data/pxc"))

# The activity sources bundled inside this plugin. One sample ships today and is served for
# every request; an authoring module comes later.
PXC_ACTIVITY_ROOT = Path(__file__).parent

# Shared with the Open edX XBlock. The XBlock signs a launch token with it and this plugin
# verifies that signature, which is what makes the learner's identity trustworthy rather than
# client-asserted. Sensitive: set it in .env.local, never in .env.
PXC_LAUNCH_SECRET = os.getenv("PXC_LAUNCH_SECRET", "")

# How long a launch token stays valid. Short: it is minted per page render.
PXC_LAUNCH_TOKEN_TTL_SECONDS = int(os.getenv("PXC_LAUNCH_TOKEN_TTL_SECONDS", "300"))

# The XBlock category the Open edX course holds. Must appear in the course's Advanced Module
# List, and the XBlock providing it must be installed in the instance (L6).
PXC_BLOCK_CATEGORY = "pxc"

# The activity type published by the "pxc" contributor. One bundled sample is served for every
# request by design (L5); an authoring module chooses per placement later.
PXC_DEFAULT_ACTIVITY = os.getenv("PXC_DEFAULT_ACTIVITY", "mcq")
