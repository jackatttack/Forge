# -*- coding: utf-8 -*-
"""The Toolbox tab: Toolbox's tools and recent scripts inside Anvil.

    if toolbox_page.available():
        board = tiles.Cards(window, on_pick=picked, extra_css=toolbox_page.css())
        board.show(toolbox_page.build_page(group))     # group: None for every tool

Built from Toolbox's own pieces (editorkit_toolbox.hub, hub_layout, tools),
so the tab shows your hub order, groups and hidden tools exactly as the hub
does, and a tap opens the tool's own window. Toolbox is optional: without
editorkit_toolbox the tab is never added, and public Forge never needs it.
"""


# --- Settings ---------------------------------------------------------------

SKIP_TOOLS = ('Forge',)      # Anvil's own Toolbox card: the tab already lives in Forge


def available():
    """Whether editorkit's Toolbox is installed here."""
    try:
        import editorkit_toolbox.hub  # noqa: F401
        return True
    except Exception:
        return False


def css():
    """The CSS file cards need on top of the card kit's."""
    from editorkit_toolbox import filecards
    return filecards.CSS


def build_page(group=None):
    """Every tool in your hub order, then recent scripts; or one group's
    tools after a Back card. Plugin files are read fresh each time."""
    from editorkit_toolbox import hub, hub_layout, tools
    tools.load()
    settings = hub_layout.load()
    if group is not None:
        specs = [hub.BACK_CARD] + [hub.tool_card(tool) for tool in group['group']]
        recent = ()
    else:
        shown = [tool for tool in hub_layout.arrange(tools.TOOLS, settings)
                 if tool['name'] not in SKIP_TOOLS]
        specs = [hub.tool_card(tool) for tool in shown]
        recent = hub.recent_files()[:settings['recent']]
    return hub.hub_page(specs, recent=recent, intro=False,
                        min_width=hub_layout.card_width(settings))