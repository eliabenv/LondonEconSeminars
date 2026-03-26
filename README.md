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
6. Building a publishable static website for GitHub Pages.

## What It Scrapes

- `LSE`: department biweekly seminar listings.
- `UCL`: department seminar page plus linked weekly detail pages.
- `QMUL`: School of Economics and Finance external seminars page.
- `LBS`: economics seminar page.
- `KCL`: King's Business School seminar series and economics brownbag series.
- `Imperial`: Economics & Public Policy seminars page.
- `IFS`: official upcoming events page.
- `OCE-EBRD`: OCE seminar-series page from Francesco Loiacono's webpage.

Notes:

- `UCL` publishes detailed speaker/title information on linked weekly pages. If those links are not yet published for the current term, the tracker may show no UCL events.
- `LBS` has recently exposed only past seminars on its official page. The parser is wired up, but you may see zero upcoming LBS events until the page is updated.
- `Imperial` currently lists 2026 dates, speakers and titles on the source page, but not explicit times/venues in the visible page text. The tracker uses a 13:30-14:45 placeholder and marks the venue as unspecified.
- `IFS` is currently scraped from the official upcoming events page rather than a structured seminar table, because the seminar page does not expose upcoming entries in a parser-friendly format.
- `OCE-EBRD` is currently sourced from the OCE seminar-series page from Francesco Loiacono's webpage, which lists weekly speakers, titles and times but not venues.

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

### Build the publishable website

```bash
python3 main.py site --refresh --days 60 --digest-days 7 --output-dir site
```

This writes:

- `site/index.html`: landing page with a button to the calendar
- `site/calendar.html`: the calendar page
- `site/weekly_digest.html`: a short digest page
- `site/seminars.json`: the raw snapshot

### Serve the dashboard

```bash
python3 main.py serve --host 127.0.0.1 --port 8000 --refresh-on-start
```

The dashboard includes an `Open Calendar` link that opens the same data in a month-grid calendar view.

## Publish It As A Web Link

The repository now includes a GitHub Actions workflow at `.github/workflows/publish_calendar.yml`.
It does three things on GitHub's servers:

1. Runs the offline tests.
2. Refreshes the seminar snapshot from the live source pages.
3. Builds a static website with a landing page, a calendar page and update links, then publishes it to GitHub Pages.

The workflow runs in three cases:

- when you push to the `main` or `master` branch
- when you start it manually from the `Actions` tab
- every Monday at `07:00 UTC`

### Turn It On

1. Push this project to a GitHub repository.
2. In GitHub, open `Settings` then `Pages`.
3. Under `Build and deployment`, choose `GitHub Actions`.
4. Open the `Actions` tab and run `Publish Seminar Calendar` once.
5. After the first run finishes, GitHub will show a stable Pages link such as `https://your-org.github.io/your-repo/`.

The published site contains:

- `index.html`: landing page with an `Open Calendar` button
- `calendar.html`: the seminar calendar
- `weekly_digest.html`: the next 7 days in digest form
- `seminars.json`: the latest raw snapshot

The landing page and calendar page both show the most recent refresh time. This is the right design for GitHub Pages, because Pages is static: it can serve the latest finished refresh immediately, but it cannot quietly re-scrape all source pages every time a visitor clicks without adding delay and extra infrastructure.

### Manual Update For Colleagues

Give your colleagues write access to the GitHub repository. They can then update the site in two ways:

- edit the scraper or documentation and push changes to the main project branch
- open the `Actions` tab and manually run `Publish Seminar Calendar`

They do not need to edit the HTML file directly. The HTML is rebuilt automatically from the latest seminar data each time the workflow runs.

If someone wants to update it from their own machine instead of GitHub, the manual sequence is:

```bash
python3 main.py refresh
python3 main.py site --days 60 --digest-days 7 --output-dir site
```

## Testing

Run the offline tests with:

```bash
python3 -m unittest discover -s tests -v
```
