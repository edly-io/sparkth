"""Organization structure: units, memberships, and their management.

A distinct domain from the permission engine — nothing in ``can()`` reads it. The
organization tree classifies people (who sits where); its permission effect arrives only
later, indirectly, through rule-driven group membership. Public surface:
``sparkth.lib.organization``.
"""
