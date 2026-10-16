# Juno adapter

Runs Portable Forge in Juno (Jupyter for iOS) from the clipboard.

    forge_entry.py      clipboard bridge; Forge works in Juno's Documents
    juno_clipboard.py   UIPasteboard through ctypes (Juno has no clipboard module)

Install or update with the Juno bootstrap (bootstrap/juno.py). It installs
the runtime into Documents/site-packages, Forge home into Documents/.forge,
and these two files into Documents.

Run forge_entry.py with a bundle on the clipboard, by hand or from a
Shortcut. The packet comes back on the clipboard, and App: juno shows in
every packet.