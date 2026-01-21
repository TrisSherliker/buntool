# Page Range Mapping - Advanced Custom Numbering

## Overview

An advanced extension to the custom alphanumeric numbering feature that allows mapping specific document page ranges to different custom numbering schemes. This enables complex scenarios like:

- **Pages 1-20**: Numbered as A1-A20 (Pleadings)
- **Pages 21-40**: Numbered as B1-B20 (Evidence)
- **Pages 41-60**: Numbered as C1-C20 (Judgment)

Each range gets its own sequential numbering with a custom prefix.

---

## How It Works

### Traditional Custom Numbering
```
Settings:
- Prefix: "A"
- Reset Mode: Sequential

Result:
Page 1 → A1
Page 2 → A2
...
Page 100 → A100
```

### Page Range Mapping (NEW)
```
Settings:
- Enable page range mapping: YES
- Mapping:
  1-20:A
  21-40:B
  41-60:C

Result:
Page 1 → A1
Page 5 → A5
Page 20 → A20
Page 21 → B1 (restarts at 1)
Page 40 → B20
Page 41 → C1 (restarts at 1)
Page 60 → C20
```

---

## Features

### ✅ Benefits
- Different numbering schemes for different sections
- Automatic sequential numbering within each range
- Easy mapping definition (CSV-like format)
- Clear visual separation of document sections
- Works with physical document tabs/dividers

### ✅ Capabilities
- Unlimited number of ranges
- Any text prefix per range (A, Doc, Section, etc.)
- Ranges can be any size
- Non-overlapping ranges (overlapping handled gracefully)
- Ranges in any order (automatically sorted)

---

## Usage Guide

### Step 1: Enable Page Range Mapping

In the "Page Numbering Options" section:
```
☑ Enable custom mapping for specific page ranges
```

### Step 2: Define Your Ranges

Enter page ranges in the text area that appears:

```
Format: start-end:prefix

Example:
1-20:A
21-40:B
41-60:C
```

**What each line means:**
- `1-20:A` = Pages 1 through 20 are numbered A1 through A20
- `21-40:B` = Pages 21 through 40 are numbered B1 through B20
- `41-60:C` = Pages 41 through 60 are numbered C1 through C20

### Step 3: Create Bundle

Click "Create Bundle" and the PDF will have custom page numbering per your ranges.

---

## Practical Examples

### Example 1: Legal Document Bundle
```
Ranges:
1-15:Pleadings
16-30:Evidence
31-50:Witness
51-60:Judgment

Result:
- Pleadings1-Pleadings15
- Evidence1-Evidence15
- Witness1-Witness20
- Judgment1-Judgment10
```

### Example 2: Court Bundle with Tabs
```
Ranges:
1-25:Tab-A
26-50:Tab-B
51-75:Tab-C
76-100:Tab-D

Result:
- Tab-A1 through Tab-A25
- Tab-B1 through Tab-B25
- Tab-C1 through Tab-C25
- Tab-D1 through Tab-D25
```

### Example 3: Multi-Document Set
```
Ranges:
1-10:Doc-A
11-20:Doc-B
21-35:Doc-C

Result:
- Document A pages 1-10 numbered: Doc-A1 to Doc-A10
- Document B pages 11-20 numbered: Doc-B1 to Doc-B10
- Document C pages 21-35 numbered: Doc-C1 to Doc-C15
```

### Example 4: Trial Bundle
```
Ranges:
1-5:Cover
6-15:TOC
16-40:Pleadings
41-100:Evidence
101-120:Judgment

Result:
- Cover pages: Cover1-Cover5
- Table of Contents: TOC1-TOC10
- Pleadings: Pleadings1-Pleadings25
- Evidence: Evidence1-Evidence60
- Judgment: Judgment1-Judgment20
```

---

## Advanced Scenarios

### Scenario 1: Physical Tabs with Consistent Numbering
**Goal**: Print document with 5 physical tabs, each tab has consistent numbering

```
Number of pages: 100
Pages per tab: 20

Configuration:
1-20:A
21-40:B
41-60:C
61-80:D
81-100:E

Print Settings:
- Print tabs labeled: A, B, C, D, E
- Tab A contains pages A1-A20
- Tab B contains pages B1-B20
- And so on...

Result:
User can easily find pages: "Go to tab B, page B7"
```

### Scenario 2: Mixed Document Types
**Goal**: Different types of documents need different numbering

```
Configuration:
1-10:Pl (Pleadings)
11-40:Ev (Evidence)
41-50:WS (Witness Statements)
51-100:J (Judgment Notes)

Result:
- Pleadings: Pl1-Pl10
- Evidence: Ev1-Ev30
- Witness: WS1-WS10
- Judgment: J1-J50
```

### Scenario 3: Large Bundle with Sections
**Goal**: 500-page bundle with clear section markers

```
Configuration:
1-50:A
51-100:B
101-150:C
151-200:D
201-250:E
251-300:F
301-350:G
351-400:H
401-450:I
451-500:J

Result:
Each 50-page section clearly marked with letters A-J
Easy reference: "See page H23" means Section H, page 23
```

---

## Format Specification

### Input Format

```
start-end:prefix
```

### Rules
- **Lines**: One range per line
- **start**: Integer, first page of range (inclusive)
- **end**: Integer, last page of range (inclusive)
- **prefix**: Any text (letters, numbers, words)
- **Separator**: Colon (`:`) between page range and prefix
- **Comments**: Empty lines are ignored
- **Order**: Ranges can be in any order (auto-sorted)

### Valid Examples
```
1-20:A
21-40:B
41-50:Doc
1-10:Section-A
11-25:Section-B
1-15:WS
16-30:Ev
31-50:Judgment
```

### Invalid Examples (Will Be Skipped)
```
1-20  (missing prefix)
20-1:A (start > end)
1:20:A (wrong format)
1..20:A (wrong separator)
```

---

## Error Handling

### Overlapping Ranges
If ranges overlap, the system uses the first matching range:

```
Ranges:
1-20:A
15-30:B (overlaps with first range)

Result:
- Pages 1-14: A1-A14
- Page 15: A15 (matches first range)
- Page 20: A20 (matches first range)
- Pages 21-30: B2-B11 (second range starts here)
```

### Gap in Ranges
If a page doesn't match any range, it falls back to global custom numbering:

```
Ranges:
1-10:A
20-30:B

Result:
- Pages 1-10: A1-A10
- Pages 11-19: 11, 12, 13... (falls back to plain numbers)
- Pages 20-30: B1-B11
```

### Invalid Ranges
Invalid ranges are skipped with a warning in the logs:

```
Valid range: 1-20:A ✅
Invalid: 20-1:B (start > end) ⚠️ SKIPPED
Invalid: 1-20 (missing prefix) ⚠️ SKIPPED
Valid range: 21-40:C ✅
```

---

## Technical Details

### Processing Flow
```
User Input
    ↓
parse_page_range_mapping()
    └─ Parse CSV-like format
    └─ Validate ranges
    └─ Sort by start page
    ↓
BundleConfig.page_range_mapping
    └─ Store parsed ranges
    ↓
For Each Page:
    └─ get_custom_number_for_page_in_range()
    └─ Check which range page falls into
    ↓
reportlab_footer_config()
    └─ Use mapped prefix if found
    └─ Fall back to global settings if not in any range
    ↓
Footer Display
    └─ Shows custom page number
```

### Algorithm
1. Parse all ranges from input string
2. Sort ranges by start page
3. For each page number, find matching range
4. If found: use range's prefix + page_within_range
5. If not found: use global custom numbering
6. Apply prefix + number to footer

---

## Logging & Debugging

### What Gets Logged
```
....Page range mapping: ENABLED
......Pages 1-20 → prefix 'A'
......Pages 21-40 → prefix 'B'
......Pages 41-60 → prefix 'C'
```

### Check Points
1. Verify ranges are parsed correctly in logs
2. Check that each page gets correct prefix
3. Look for warnings about invalid ranges
4. Confirm page numbers restart at 1 for each range

### View Logs
```
logs/buntool_[SESSION_ID].log
```

Search for "Page range mapping" to see all details.

---

## Comparison: With vs Without Range Mapping

### Without Range Mapping (Old Feature)
```
Configuration:
- Prefix: A
- Mode: Sequential

Result:
A1, A2, A3, ..., A100
(All pages have same prefix)
```

### With Range Mapping (New Feature)
```
Configuration:
1-25:A
26-50:B
51-75:C
76-100:D

Result:
A1-A25, B1-B25, C1-C25, D1-D25
(Different prefixes for different sections)
```

---

## FAQ

**Q: Can I use the same prefix for multiple ranges?**
A: Yes! Each range is independent.

```
1-20:Doc
21-40:Doc
41-60:Doc

Result: Doc1-Doc20, Doc1-Doc20, Doc1-Doc20 (resets each range)
```

**Q: What happens if I don't cover all pages?**
A: Uncovered pages fall back to global custom numbering (if set) or plain numbers.

**Q: Can ranges be in any order?**
A: Yes! They're automatically sorted:
```
41-60:C
1-20:A
21-40:B

Gets sorted to: A (1-20), B (21-40), C (41-60)
```

**Q: Can I use long prefixes?**
A: Yes! Any text works: "Section-A", "Evidence-Tab", "Pleading", etc.

**Q: Does range mapping work with other options?**
A: Yes! Works with:
- All font options (serif, sans, mono, traditional)
- All alignments (left, center, right)
- Footer prefix option
- Roman numeral preface
- All other numbering styles (when not using custom_alpha)

**Q: What's the maximum number of ranges?**
A: No limit! Define as many as needed.

---

## Best Practices

1. **Start Small**: Test with 2-3 ranges first
2. **Keep Prefixes Short**: 1-3 characters is ideal
3. **Cover All Pages**: Define ranges for the entire document
4. **Use Meaningful Prefixes**: "Ev" for Evidence, "WS" for Witness
5. **Verify in Logs**: Always check logs for parsing results
6. **Test Print**: Print a sample to verify tab alignment

---

## Troubleshooting

### Pages Not Numbered Correctly
1. Check the logs for parsing warnings
2. Verify range syntax: `start-end:prefix`
3. Ensure all ranges are valid (start ≤ end)
4. Confirm page numbers don't exceed document length

### Prefix Cut Off
- Use shorter prefixes
- Change alignment (center/left instead of right)

### Pages Missing Range Coverage
- Add more ranges to cover all pages
- Uncovered pages default to global numbering

### Overlapping Ranges
- First matching range wins
- Reorder ranges if needed
- Or redefine to avoid overlaps

---

## Examples in the Wild

### Legal Practice
```
1-10:Pleadings
11-25:Evidence-Docs
26-40:Evidence-Photos
41-45:Witness-Statements
46-50:Court-Orders
```

### Medical Case
```
1-5:Cover
6-10:Summary
11-20:Medical-Records
21-35:Expert-Reports
36-50:Photos-Imaging
```

### Business Dispute
```
1-25:Contracts
26-50:Correspondence
51-75:Financial-Statements
76-100:Email-Evidence
```

---

## Version Information

- **Feature Version**: 2.0 (Page Range Mapping)
- **Base Version**: 1.0 (Custom Alphanumeric)
- **Release Date**: January 2026
- **Compatibility**: BunTool 2025-01-24+
- **Status**: Production Ready

---

**Page Range Mapping Feature Documentation**
Complete and ready for production use.
