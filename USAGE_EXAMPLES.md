# Custom Alphanumeric Numbering - Usage Examples

## Real-World Scenarios

### Scenario 1: Legal Document Bundles with Section Markers
**Use Case:** A court bundle with multiple sections, each needs separate numbering

**Configuration:**
- Numbering Style: Custom Alphanumeric
- Prefix: "Pt" (for "Part")
- Reset Mode: Letter per 26 pages

**Result:**
```
Pt A1 (Part A, page 1)
Pt A2 (Part A, page 2)
...
Pt A26 (Part A, page 26)
Pt B1 (Part B, page 1)
Pt B2 (Part B, page 2)
```

**Benefit:** Easy to reference parts in court proceedings ("see Pt B5")

---

### Scenario 2: Multi-Tab Document Set
**Use Case:** Each physical tab in a printed bundle has its own numbering

**Configuration:**
- Numbering Style: Custom Alphanumeric
- Prefix: "" (empty)
- Reset Mode: Reset every 20 pages

**Result:**
```
Tab 1 (pages 1-20):   A1, A2, ..., A20
Tab 2 (pages 21-40):  B1, B2, ..., B20
Tab 3 (pages 41-60):  C1, C2, ..., C20
```

**Benefit:** Physical tabs align with PDF numbering

---

### Scenario 3: Witness Statement Bundle
**Use Case:** Each witness statement has separate numbering

**Configuration:**
- Numbering Style: Custom Alphanumeric
- Prefix: "WS" (for Witness Statement)
- Reset Mode: Sequential

**Result:**
```
WS1, WS2, WS3, ..., WS150
```

**Benefit:** Simple sequential numbering with prefix for clarity

---

### Scenario 4: Trial Bundle with Document Classes
**Use Case:** Different document types in separate sections

**Configuration per section:**
- Section A (Pleadings): Prefix="Plead", Reset="Sequential"
  - Result: Plead1, Plead2, Plead3, ...
  
- Section B (Evidence): Prefix="Ev", Reset="Letter change (every 26)"
  - Result: EvA1, EvA2, ..., EvA26, EvB1, ...
  
- Section C (Judgment): Prefix="J", Reset="Every 30 pages"
  - Result: JA1-JA30, JB1-JB30, JC1-JC30, ...

**Benefit:** Each section clearly identified with appropriate numbering scheme

---

## Advanced Use Cases

### Use Case: Tab Index Integration
**Problem:** Need to print tabs with matching PDF numbering

**Solution:**
1. Determine how many pages per physical tab
2. Set Reset Mode to "Reset every N pages"
3. Match N with your physical tab page count
4. Print tabs labeled A, B, C, etc.
5. Print PDF with matching pagination

**Example:**
- 5 physical tabs, 40 pages total (~8 pages per tab)
- Set: Custom Alpha, Prefix="", Reset every 8 pages
- Result: A1-A8, B1-B8, C1-C8, D1-D8, E1-E8
- Print tabs labeled A, B, C, D, E

---

### Use Case: Reference System for Emails
**Problem:** Need to cite pages in correspondence

**Solution:**
Use meaningful prefix that appears in emails

**Configuration:**
- Prefix: "RE-" (for document reference)
- Reset: Sequential
- Result: RE-1, RE-2, RE-3, ..., RE-100

**Benefit:** Easy to write in emails: "see page RE-47"

---

## Comparison: When to Use Which Mode

| Reset Mode | Best For | Example |
|-----------|----------|---------|
| Sequential | Simple, continuous numbering | "Doc1" through "Doc500" |
| Letter Change | Natural 26-page grouping | "EvA1-EvA26, EvB1-EvB26" |
| Custom Interval | Matching physical tabs or sections | 20-page sections: "A1-A20, B1-B20" |

---

## Tips & Tricks

### Tip 1: International Characters
**Can I use numbers in other languages?**
Currently optimized for English letters (A-Z). Works with any text prefix though:
- "第1章1" (Japanese: Chapter 1)
- "Chapitre1" (French: Chapter)
- Custom prefixes work with any UTF-8 text

### Tip 2: Longer Prefixes
**What if I use a 10-character prefix?**
No problem! Any length prefix works:
- Prefix: "EVIDENCE-TAB" → "EVIDENCE-TAB1", "EVIDENCE-TAB2", ...

### Tip 3: Combining with Other Settings
**Can I use custom numbering with roman preface?**
Yes! Complete compatibility:
- Preface uses roman numerals: i, ii, iii, ...
- Main content uses custom alpha: A1, A2, A3, ...
- Frontmatter offset is automatically calculated

### Tip 4: Font Styling
**Does font selection affect custom numbering?**
No, custom numbering works with all fonts:
- Traditional (Charter)
- Serif (Times)
- Sans-serif (Helvetica)
- Mono (Courier)

### Tip 5: Pre-numbering Your Files
**Can I use custom numbering with CSV index?**
Yes, completely independent:
- CSV index determines document titles and descriptions
- Custom numbering only affects the footer page numbers
- Both work together seamlessly

---

## Common Mistakes & Solutions

### ❌ Mistake 1: Forgetting Reset Interval
- **Problem:** Selected "Reset every N pages" but didn't set interval
- **Solution:** Always ensure interval is set when using custom reset

### ❌ Mistake 2: Very Long Prefix + Long Bundles
- **Problem:** "VeryLongPrefix100" takes up too much footer space
- **Solution:** Keep prefix short (1-3 characters) for long bundles

### ❌ Mistake 3: Mixing Reset Modes
- **Problem:** Expecting "letter change" to reset at intervals
- **Solution:** Choose ONE reset mode; they don't combine

### ❌ Mistake 4: Not Accounting for Frontmatter
- **Problem:** Expected first document to be "A1" but got offset
- **Solution:** This is correct! Frontmatter has different numbering (roman numerals or no number)

---

## Logging & Troubleshooting

When custom numbering is used, the bundle creation log will show:

```
....Page numbering style: custom_alpha
....Custom alpha prefix: A
....Custom alpha reset mode: letter_change
```

Check the log file (located in `logs/buntool_[SESSION_ID].log`) to verify your settings were correctly passed through.

---

## Future Enhancement Ideas

1. **Reverse Numbering**: Z1, Z2 down to A1, A2
2. **Roman + Alpha**: i, ii, iii in preface; A1, A2 in main
3. **Custom Separators**: "A-1" instead of "A1", "A_1", etc.
4. **Multi-Part Prefixes**: "Chapter-A-1", "Chapter-B-1"
5. **Auto-Prefix from Metadata**: Derive prefix from PDF metadata or CSV data
