# 0025 · Persistent section navigation

Status: implemented, user comprehension pending. The active market and current section must remain identifiable as the page scrolls.

## Interaction

- Use one sticky header for the active market, data status and section links. The market chip returns to the selector. The primary navigation stays available on narrow screens in its own horizontally scrollable row.
- Highlight the section nearest the reading line as the user scrolls. Use the same indication for direct section links, keyboard navigation and return visits. Preserve fragment URLs and the previous chart aliases.
- Offset scroll targets and the findings index by the measured header height. Keep focus visible and honor reduced-motion preferences. Preserve the native links when report data is unavailable.
- Keep the market label visible while reading historical sections. Switching markets updates the label and evidence together.

## Acceptance and ownership

The Product Lead owns whether a reader can answer “what market am I viewing, where am I, and how do I get to the next section?” Design owns layout and focus visibility. QA covers keyboard, direct links, scroll position, market changes, mobile overflow and reduced motion. The release operator checks the published build. Include a task in the SPY pilot that asks the reader to move from Levels to Data and return to the market selector without losing the selected instrument.
