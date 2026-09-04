# URL

## Summary

URL probes, fetches, parses, or downloads HTTP and HTTPS resources.

Use it when Forge needs a bounded request to an external resource.

## Modes

Fetch readable page content:

    URL https://example.com
    MODE: fetch

`fetch` is the default. `STRIP: markdown` produces a compact approximation
suited to a Forge packet.

Probe metadata without fetching the response body:

    URL https://example.com
    MODE: probe

Probe sends a HEAD request and reports status, content type, content length,
and the final URL.

Parse JSON:

    URL https://api.example.com/catalogue
    MODE: json

Download a resource into the project:

    URL https://example.com/files/report.pdf
    MODE: download
    DEST: downloads/report.pdf

Download mode requires a project-relative `DEST`. The resolved destination
must remain inside the project root.

## JSON selection

`JPATH` is a small dotted accessor, not full JSONPath.

Dictionary keys use their names and list elements use numeric indexes. Given:

    {
      "data": {
        "items": [
          {"title": "First"},
          {"title": "Second"}
        ]
      }
    }

this selects `First`:

    URL https://api.example.com/catalogue
    MODE: json
    JPATH: data.items.0.title

Retry without `JPATH` when the response shape is uncertain.

## Fetch cleanup

`STRIP` applies to fetch mode:

- `STRIP: markdown` extracts compact headings, links, and readable text
- `STRIP: plain` removes HTML tags and normalises whitespace
- `STRIP: no` keeps the decoded response text

The default is `markdown`.

## Headers and credential safety

A non-sensitive request header may be supplied as `Name=value`:

    URL https://api.example.com/catalogue
    MODE: json
    HEADERS: Accept=application/json

Never put an Authorization header, cookie, API key, bearer token, session
token, or any other credential in `HEADERS`.

Forge stores submitted bundles in run history. A secret written in a directive
would therefore be copied into `.forge` run artifacts and may also appear in a
returned packet or chat transcript.

Use a dedicated operation that reads credentials from a local secret file when
authenticated access is required.

## Directives

- `MODE: fetch|probe|json|download` selects request behavior; default `fetch`.
- `DEST: path` sets the project-relative download destination.
- `FOLLOW_REDIRECTS: yes|no` controls redirects; default `yes`.
- `HEADERS: Name=value` adds one non-sensitive HTTP request header.
- `JPATH: dotted.path.0.key` selects part of a JSON response.
- `STRIP: markdown|plain|no` controls fetch cleanup; default `markdown`.
- `TIMEOUT: N` sets a positive timeout in seconds; default `20`.

## Output limits

Fetch and JSON previews are capped at 80 output lines. If additional lines are
omitted, the preview reports how many remain.

This preview limit does not limit the bytes read from the network or written
by download mode.

## Safety and limits

The target must begin with `http://` or `https://`.

Use `MODE: probe` before fetching an unfamiliar endpoint. A server may reject
HEAD even when GET would succeed, so a failed probe does not prove the
resource is unavailable.

Network and HTTP failures produce a failed operation. Redirects are followed
by default.

URL does not execute downloaded content. Inspect a downloaded text or Python
file with READ before using it.