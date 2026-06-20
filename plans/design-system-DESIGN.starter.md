# DESIGN.md (starter)

Drop this into the `design-system` repo root as `DESIGN.md` and refine. It is
the single source of taste; a target may copy and re-skin it. Token values here
must mirror the Tailwind preset — keep them in sync.

**Style:** simple SaaS — blue & white, minimalist. Calm, content-first, generous
whitespace, one blue accent, restrained type and shadow. Depth comes from
hairline borders + subtle shadows, not from color. All values below are generic
starting points; tune to taste.

## Palette
- Canvas: `#ffffff`
- Subtle background (sections/inputs): `#f6f8fb`
- Card / surface: `#ffffff` (raised by border + shadow, not fill)
- Text primary: `#0f172a`
- Text secondary: `#5b6675`
- Border / hairline: `#e6eaf0`
- **Accent (primary): `#2563eb`** · hover `#1d4ed8` · tint `#eef3ff`
- Focus ring: `#2563eb` at 40% opacity
- Status (use sparingly): success `#15a34a` · warning `#c2700a` · danger `#dc2626`

## Typography
- Family: **Inter** for everything (UI, body, headings) — one family, weights do
  the work. OFL-licensed, free to bundle. (Optional display alt: Space Grotesk.)
- Scale (size / line-height): Display 40 / 1.15 · H1 30 / 1.2 · H2 24 / 1.3 ·
  H3 20 / 1.35 · Body 16 / 1.55 · Small 14 / 1.5 · Caption 12 / 1.4
- Weights: 400 body · 500 UI labels · 600 headings
- Tracking: `-0.01em` on headings ≥ 24px; `0` elsewhere

## Spacing (4px base scale)
`4, 8, 12, 16, 24, 32, 48, 64, 96`. Card padding 24. Section vertical rhythm 64
(compact) / 96 (marketing). Related-element gap 8–12.

## Radius
Consistent and modest: controls (button/input) `8`, cards `12`, pills/badges
`999`. Avoid mixing more than two radius profiles in one component cluster.

## Elevation
- sm: `0 1px 2px rgba(15,23,42,0.06)` — inputs, resting cards
- md: `0 4px 12px rgba(15,23,42,0.08)` — popovers, raised cards
Never shadow plain text or structural dividers.

## Layout
Max content width `1120px`, centered. Generous gutters. Prefer a clear grid and
whitespace over borders to separate regions.

## Components (v1)
- **Button / primary:** bg accent, white text, radius 8, weight 500; hover →
  accent-hover. One primary per view region.
- **Button / secondary:** white bg, primary text, 1px border, radius 8.
- **Button / ghost:** transparent, secondary text, hover → subtle background.
- **Input:** white bg, 1px border, radius 8, 12×14 padding; focus → accent ring,
  border accent. Placeholder = text-secondary.
- **Card:** white bg, 1px hairline border, radius 12, padding 24, shadow sm.

## Do / Don't
- **Do** lead with whitespace and hierarchy; let one accent carry emphasis.
- **Do** keep neutrals truly neutral; reserve blue for interaction/emphasis.
- **Don't** use pure black for text or fills — use `#0f172a`.
- **Don't** add more than one accent hue, or shadows heavier than `md`.
- **Don't** decorate; if an element doesn't aid comprehension, remove it.

## Tokens (mirror in the Tailwind preset)
```css
:root {
  --color-canvas: #ffffff;
  --color-subtle: #f6f8fb;
  --color-text: #0f172a;
  --color-text-secondary: #5b6675;
  --color-border: #e6eaf0;
  --color-accent: #2563eb;
  --color-accent-hover: #1d4ed8;
  --color-accent-tint: #eef3ff;
  --radius-control: 8px;
  --radius-card: 12px;
  --font-sans: 'Inter', system-ui, sans-serif;
}
```
Tailwind utility names to expose: `bg-canvas` `bg-subtle` `text-default`
`text-secondary` `border-hairline` `bg-accent` `text-accent` `rounded-control`
`rounded-card` `font-sans`.
