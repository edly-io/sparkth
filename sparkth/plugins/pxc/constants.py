from pathlib import Path

# The activity sources bundled inside this plugin. One sample ships today and is served for
# every request; an authoring module comes later.
PXC_ACTIVITY_ROOT = Path(__file__).parent

# The XBlock category the Open edX course holds. Fixed rather than configurable: it must equal
# the name of the entry point the XBlock registers, and a configurable value could drift out of
# sync with the installed package (L6).
PXC_BLOCK_CATEGORY = "pxc"
