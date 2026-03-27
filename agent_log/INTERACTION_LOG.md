# Interaction Log

## 2026-03-26

- User asked how to make the seminar calendar available through a stable web link and requested a GitHub Actions workflow.
- Added a workflow that refreshes seminar data, rebuilds the HTML outputs, and deploys them to GitHub Pages.
- Added README instructions describing how to enable Pages and how colleagues can trigger updates.
- User reported that the `Build and deployment` section was not visible in the GitHub Pages settings.
- Checked current GitHub documentation to identify the likely blockers: missing admin or maintainer rights, unsupported repository visibility or plan, or repository-level restrictions on Pages or Actions.
- User then reported that a run labelled `Added publish_calendar.yml` failed while `Publish Seminar Calendar` succeeded.
- Interpreted this as most likely an older push-triggered run tied to the commit message rather than a separate workflow definition.
- User asked for a GitHub Pages landing page with one clear button to the calendar, visible last-updated information, and a repository link with manual update instructions.
- Added a new `site` build command, a static homepage renderer, last-updated labels on the calendar, and repository/manual-update links suitable for GitHub Pages.
- Updated the publication workflow to deploy the generated homepage at `index.html` and the calendar at `calendar.html`.
- User asked where the Pages homepage can be found.

## 2026-03-27

- User asked for a README link that takes readers directly to the published tracker.
- Added the live GitHub Pages tracker link near the top of the README using the repository's GitHub Pages URL pattern.
