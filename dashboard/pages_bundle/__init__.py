"""Page modules for the CRYOSYNC dashboard.

Each module in this package exports exactly one ``render()`` function and is
registered in :mod:`core.registry`. A page owns its own reasoning and layout;
it loads data through :mod:`core.dataset`, formats through
:mod:`core.formatting`, and draws with :mod:`ui.components`, so no page ever
reads a file or hard-codes a colour.
"""
