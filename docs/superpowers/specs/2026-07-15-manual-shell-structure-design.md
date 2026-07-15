# Manual Shell Structure Repair

## Problem

`fields.html`, `create.html`, `plot.html`, and `tessellations.html` close their
`<main class="wrap">` element before the article is finished. The shared
documentation script consequently appends the previous/next pager in the
middle of each article. Later headings disappear from the page table of
contents, and later figures size themselves against the viewport instead of
the 780 px reading column.

## Design

Keep the complete article—including its footer—inside the single `<main>` on
every manual page. Replace the obsolete trailing `</div>` wrappers with the
correct final `</main>` and make no visual or content changes.

Add a structural regression check that parses each manual page, tracks whether
headings, figures, and footers occur inside `<main>`, and requires the main
element to remain open until the article footer. Existing link, image, schema,
and browser checks remain unchanged.

## Verification

- The new structural test fails on the four affected pages before the repair.
- All documentation and frontend contract tests pass after the repair.
- Browser inspection confirms 780 px maximum figure width, complete TOCs, and
  the pager after the footer on desktop and mobile layouts.
