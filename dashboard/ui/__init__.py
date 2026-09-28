"""Presentation layer for the CRYOSYNC dashboard.

``ui`` owns everything the operator sees but never decides anything: the
stylesheet, the persistent shell (top bar and sidebar) and the small set of
reusable layout primitives every page composes from. Keeping this separate from
``core`` means a page module contains only its own reasoning, and the chrome
looks identical everywhere because it is written once.
"""
