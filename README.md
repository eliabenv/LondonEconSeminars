# London Economics Seminar Tracker

A small Python application that pulls seminar listings from official pages for:

- LSE
- UCL
- QMUL
- LBS
- KCL
- Imperial
- IFS
- OCE-EBRD

It supports four things:

1. Refreshing a local seminar snapshot from the live source pages.
2. Printing a weekly digest in the terminal.
3. Sending that digest by email through SMTP.
4. Serving a local browser dashboard.
5. Writing a standalone HTML calendar view.

## What It Scrapes

- `LSE`: department biweekly seminar listings.
- `UCL`: department seminar page plus linked weekly detail pages.
- `QMUL`: School of Economics and Finance external seminars page.
- `LBS`: economics seminar page.
- `KCL`: King's Business School seminar series and economics brownbag series.
- `Imperial`: Economics & Public Policy seminars page.
- `IFS`: official upcoming events page.
- `OCE-EBRD`: OCE seminar-series page supplied by the user.

Notes:

- `UCL` publishes detailed speaker/title information on linked weekly pages. If those links are not yet published for the current term, the tracker may show no UCL events.
- `LBS` has recently exposed only past seminars on its official page. The parser is wired up, but you may see zero upcoming LBS events until the page is updated.
- `Imperial` currently lists 2026 dates, speakers and titles on the source page, but not explicit times/venues in the visible page text. The tracker uses a 13:30-14:45 placeholder and marks the venue as unspecified.
- `IFS` is currently scraped from the official upcoming events page rather than a structured seminar table, because the seminar page does not expose upcoming entries in a parser-friendly format.
- `OCE-EBRD` is currently sourced from the OCE seminar-series page provided by the user, which lists weekly speakers, titles and times but not venues.

## Requirements

- Python 3.13 or newer.
- Network access when you run refreshes.

The project uses only the Python standard library, so there is no package install step.
If your local Python CA bundle is broken, the fetch layer falls back to `curl`, which usually fixes certificate errors on macOS.

## Quick Start

Run a refresh and print the next week's seminars:

```bash
python3 main.py refresh
python3 main.py digest --days 7
```

Start the local dashboard:

```bash
python3 main.py serve --refresh-on-start
```

Then open `http://127.0.0.1:8000`.

Write a standalone HTML calendar from the saved snapshot:

```bash
python3 main.py calendar --days 60
```

## Email Delivery

Copy `.env.example` to `.env` and fill in your SMTP details, then run:

```bash
python3 main.py send-weekly
```

If SMTP is not configured, the command still writes an HTML digest to `data/weekly_digest_latest.html`.

## CLI Commands

### Refresh source data

```bash
python3 main.py refresh --horizon-days 180
```

### Print a digest

```bash
python3 main.py digest --days 7 --refresh
python3 main.py digest --days 14 --html-output
```

### Send the weekly email

```bash
python3 main.py send-weekly --days 7
```

The app records the ISO week that was last emailed and will skip duplicate sends unless you pass `--force`.

### Write the HTML calendar

```bash
python3 main.py calendar --days 60
python3 main.py calendar --days 45 --institution LSE
python3 main.py calendar --days 90 --output data/my_calendar.html
```

The default output file is `data/seminar_calendar_latest.html`.

### Serve the dashboard

```bash
python3 main.py serve --host 127.0.0.1 --port 8000 --refresh-on-start
```

The dashboard includes an `Open Calendar` link that opens the same data in a month-grid calendar view.

## Testing

Run the offline tests with:

```bash
python3 -m unittest discover -s tests -v
```
