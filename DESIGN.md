---
name: UAE Tax and eInvoicing Readiness
description: A pale blotter for a bilingual UAE tax readiness review. One indigo action, a night bar, ruled rows.
colors:
  ink: "#28253B"
  ink-2: "#554E7B"
  line: "#E4E3EF"
  canvas: "#E7E6F2"
  paper: "#FFFFFF"
  tint: "#F4F3FB"
  lavender: "#EDECFB"
  indigo: "#5266EB"
  indigo-deep: "#3D4ED4"
  night: "#171721"
  on-dark: "#EDEDF3"
  pass: "#1D6B45"
  verify: "#7A3E24"
typography:
  display:
    fontFamily: "General Sans, Tajawal, system-ui, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "General Sans, Tajawal, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  title:
    fontFamily: "General Sans, Tajawal, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "-0.03em"
  body:
    fontFamily: "General Sans, Tajawal, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  control: "12px"
  pill: "999px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "28px"
components:
  button-primary:
    backgroundColor: "{colors.indigo}"
    textColor: "#FFFFFF"
    typography: "{typography.body}"
    rounded: "{rounded.pill}"
    height: "40px"
---

# Design System: UAE Tax and eInvoicing Readiness

## Overview

**Creative North Star: "The Blotter"**

The desk is a ruled sheet. The batch is rows. The agent handoffs are a tape on the end edge. A night bar holds the name and the seat. One indigo pill advances the review.

The earlier split login, with its violet mesh and floating card, is retired. This system is adapted from a pale finance product surface: quiet ink, one action color, tabular figures. It is Desert Ledger, not that product.

English and Arabic share the sheet. The tape moves to the opposite edge in Arabic. Amounts, identifiers, and dates stay left-to-right.

## Colors

- **Indigo** (#5266EB): the control that moves the review forward. Hover is indigo-deep (#3D4ED4).
- **Ink** (#28253B): names, row titles, and the tape role.
- **Ink-2** (#554E7B): supporting sentences. It stays dark enough to read on white.
- **Night** (#171721): the bar, and the agent trace. Text on it is #EDEDF3. Dim text on it is #B7B6C9.
- **Canvas** (#E7E6F2) is the well between sections. **Paper** (#FFFFFF) is the ledger and the question dock.
- **Line** (#E4E3EF): row rules.
- **Lavender** (#EDECFB): the unverified-inference strip, and the brief wash when a tape line arrives.
- **Pass** (#1D6B45 on #E5F4EC) and **verify** (#7A3E24 on #F8EEE6): the mark in a row. Same size. Neither is a stripe down the row.

## Typography

General Sans for Latin, Tajawal when the page is Arabic. Weight 500 for headings and the primary button, 400 for rows. Figures are tabular.

- Display, 2.5rem / 1.15: the gate headline.
- Headline, 1.75rem / 1.2: a section on the sheet.
- Title, 1.25rem / 1.3: the tenant name on the desk, and the tape title.
- Body, 1rem / 1.5.

## Layout

The bar is 64px. The landing is the review itself: the headline, the blotter, then the roles. Sign-in is a separate screen. A feature table is not the first screen. The desk sits on the canvas well: a white ledger, and a night tape. The question dock is a white panel pinned to the foot of the tape, so it stays in the first screen while the handoffs scroll. Under 960px the tape stacks under the sheet and the question dock moves above the handoffs.

## Components

- **Primary:** indigo pill, 40px, white text.
- **Quiet:** indigo tint, no border, for upload, reject, and escalate.
- **Field:** 48px, 12px radius, line border. Focus is an indigo ring.
- **Row:** a hairline, not a card. Hover is a tint.
- **Mark:** a pill word, pass or to verify.
- **Tape:** a night column. An empty tape lists the seven roles as waiting. The list scrolls inside the column.
- **Question dock:** a white panel on the night tape, with the indigo Ask control. It is a separate section from the handoffs.
