# Daily Log

## 2026-03-26

Set up the project for web publishing through GitHub Pages. The repository now has a scheduled workflow that refreshes seminar listings, rebuilds the calendar and weekly digest, and publishes a stable web link that colleagues can open. Added short setup instructions so the department can switch Pages on in GitHub and rerun the publication step when needed.

Also checked GitHub's current Pages documentation after a missing-settings report. The workflow file is still consistent with GitHub's recommended Pages deployment pattern, so the likely issue is with repository permissions, visibility, or repository settings rather than the workflow itself.

Later clarified a likely false alarm in the Actions list: a failed run label appeared to be tied to the commit that introduced the workflow file, while the actual publication workflow succeeded on a later run.

Built the next stage of the published site for departmental use. The GitHub Pages output is now a small front page with one prominent button to the calendar, plus visible update timing, a digest link, raw data access, and a repository link that points colleagues to manual update instructions. The calendar page itself now also shows when the data was last refreshed.

Clarified where the homepage lives both locally and on GitHub Pages, so the published entry point is easy to locate and share.

## 2026-03-27

Added a direct link to the published GitHub Pages tracker near the top of the README so visitors to the repository can open the live site immediately.
