# MockAI V2 Website Review Report

Date: 2026-02-18  
Requested URL: `https://mockai-v2.pruthvirajchavan.codes/`

## Scope and Method

- Attempted direct browser automation first; environment could not run Playwright Chrome on Linux Arm64.
- Performed web fetch/index-based review of linked pages and navigation paths.
- Observable site content was primarily served on `https://www.aceinterview.app/`.

## Coverage Summary

- Home: accessible
- Pricing: accessible
- Career listing + 3 role detail pages: accessible
- Blogs index + 2 blog detail pages: accessible (limited detail content in indexed fetch)
- Contact: accessible
- Sign-in: accessible (redirect from `/dash` to `/sign-in?next=/dash`)
- Privacy + Terms: accessible
- Newsletter and some links intermittently not fetchable in this environment

## Key Findings

1. Legal/entity consistency issue
- Privacy and Terms reference `LeetGPT Inc.` while product branding is `MockAI` and primary host appears as `aceinterview.app`.
- This creates trust/compliance ambiguity.

2. Copyright year inconsistency
- Footer years vary across pages (`@2025` on some pages, `@2026` on others).

3. Link/page availability inconsistency
- Some paths surfaced by navigation/search could not be fetched reliably in this environment (e.g., newsletter page and one career/blog path in direct open flow).
- This may indicate route availability/caching/indexing inconsistency.

4. Blog detail indexing/SEO weakness
- Blog detail pages often expose title/date/image metadata but little/no article body in fetch/index outputs.
- If this reflects runtime behavior, content may be too client-rendered for crawlers and weak for SEO/discoverability.

5. Minor content formatting issue
- Compensation formatting inconsistency on career content (example: one salary string missing `$` on first number).

## Positive Observations

- Clear value proposition and conversion flow (`Get Started`, free trial, sign-in).
- Good breadth of product messaging (mock interviews, reporting, targeted company practice).
- Legal pages are present and updated with explicit dates.
- Career pages are structured and detailed.

## Recommended Actions (Priority Order)

1. P0: Verify route health and indexing
- Run a production crawl (status codes + canonical URLs) for all nav/footer links and career/blog detail routes.
- Fix any non-200 pages, broken links, and redirect anomalies.

2. P1: Normalize legal identity and policy references
- Use one canonical company/entity name across Privacy, Terms, and footer.
- Confirm legal mailing/contact details match the active operating entity.

3. P1: Normalize global footer content
- Make copyright year and legal link labels consistent site-wide.

4. P1: Improve blog SSR/SEO
- Ensure full article content is server-rendered or pre-rendered for crawlers.
- Add/validate canonical, OpenGraph, and structured metadata for blog pages.

5. P2: Content QA pass
- Standardize salary/currency formatting and minor copy consistency across career pages.

## Notes

- Direct live-browser interaction was blocked by environment limitations, so this report is based on accessible indexed/fetched page content.
- For final QA, a full manual pass in a standard desktop/mobile browser is still recommended.
