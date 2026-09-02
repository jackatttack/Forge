URL is the reboot HTTP access op.

Use it when Forge needs to reach outside the local project.

Shape:

URL https://example.com
MODE: fetch

Modes:

MODE: fetch
MODE: probe
MODE: json
MODE: download

Optional:

STRIP: markdown
STRIP: plain
STRIP: no
TIMEOUT: 20
FOLLOW_REDIRECTS: yes
JPATH: data.items.0.title
DEST: downloads/file.txt

Safety rules:
- URL must start with http:// or https://
- download mode requires DEST
- DEST must remain inside the project root
- failed HTTP/network calls produce a failed run and hint block
- fetched previews are capped so packets stay usable

Preferred use:
- use MODE: probe before fetching unknown endpoints
- use MODE: json for APIs
- use MODE: download only when a local artifact is needed
