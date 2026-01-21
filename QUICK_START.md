# Custom Alphanumeric Numbering - Quick Start Guide

## 🚀 Getting Started

### Step 1: Create Your Bundle
1. Open BunTool at http://127.0.0.1:7001
2. Fill in bundle details (Title, Case Name, Claim Number)
3. Upload your PDF files

### Step 2: Select Custom Numbering
1. Scroll to "Step 3 - Page Numbering Options"
2. In the "Numbering style" dropdown, select: **"Custom Alphanumeric e.g. 'A1', 'A2', 'B1'"**

### Step 3: Configure Custom Numbering
New fields appear! Fill them in:

#### Field 1: Custom numbering prefix
- **What to enter**: A letter or text prefix
- **Examples**:
  - "A" → pages numbered: A1, A2, A3, ...
  - "Doc" → pages numbered: Doc1, Doc2, Doc3, ...
  - "" (empty) → pages numbered: 1, 2, 3, ...

#### Field 2: Reset numbering
- **Choose one**:
  - **Sequential**: Continuous (1, 2, 3, ...) or with prefix (A1, A2, A3, ...)
  - **Change letter per 26 pages**: (A1-A26, B1-B26, C1-C26, ...)
  - **Reset every N pages**: (Custom interval, see below)

#### Field 3: Reset every N pages (if applicable)
- **When visible**: Only when you selected "Reset every N pages" above
- **What to enter**: Number of pages before resetting (e.g., 20, 30, 50)
- **Example**: If set to 20: A1-A20, B1-B20, C1-C20, ...

### Step 4: Complete & Download
1. Configure other options as needed (font, alignment, etc.)
2. Click "Create Bundle"
3. Download your PDF with custom numbering!

---

## 📋 Common Configuration Templates

### Template A: Simple Prefix
```
✓ Numbering style: Custom Alphanumeric
✓ Prefix: A
✓ Reset: Sequential
→ Result: A1, A2, A3, ..., A100
```

### Template B: Auto-Incrementing Letters (Every 26 Pages)
```
✓ Numbering style: Custom Alphanumeric
✓ Prefix: (empty)
✓ Reset: Change letter per 26 pages
→ Result: A1-A26, B1-B26, C1-C26, ...
```

### Template C: Section Tabs (Every 20 Pages)
```
✓ Numbering style: Custom Alphanumeric
✓ Prefix: (empty)
✓ Reset: Reset every N pages = 20
→ Result: A1-A20, B1-B20, C1-C20, ...
```

### Template D: Complex Prefix
```
✓ Numbering style: Custom Alphanumeric
✓ Prefix: WS
✓ Reset: Sequential
→ Result: WS1, WS2, WS3, ..., WS50
```

---

## ❓ Quick FAQ

**Q: Can I use this with roman numerals for the preface?**
A: Yes! Roman numerals apply to the frontmatter (table of contents), and custom alphanumeric applies to the main content.

**Q: Does custom numbering work with all fonts?**
A: Yes! Works with all font options (Helvetica, Times, Courier, Charter).

**Q: Can I change the alignment of custom numbers?**
A: Yes! Alignment settings (Left/Center/Right) work independently.

**Q: What if I want numbers to go beyond Z?**
A: Automatically continues to AA, AB, BA, BB, etc. (all combinations possible)

**Q: Does custom numbering affect the table of contents?**
A: No, table of contents is separate. Custom numbering only affects the page footer.

**Q: Can I use special characters in the prefix?**
A: Yes, but stick to letters and numbers for best results. Special characters may not display correctly.

---

## 🔍 Verification Checklist

After creating your bundle, verify:

- [ ] First page has expected numbering (e.g., "A1" or "A1" with correct prefix)
- [ ] Numbers increment correctly through the document
- [ ] Letters change at expected intervals (if using letter change or interval reset)
- [ ] Numbers are aligned as selected (left/center/right)
- [ ] Font is readable and matches your selection
- [ ] Frontmatter uses roman numerals (if enabled)

---

## 🐛 Troubleshooting

### Issue: Custom numbering fields don't appear
- **Solution**: Make sure you selected "Custom Alphanumeric" from the dropdown

### Issue: Numbers aren't showing in the PDF
- **Solution**: Check page alignment (might be off-page). Try "Center" alignment.

### Issue: Pages numbering incorrectly after interval reset
- **Solution**: Verify the reset interval. It should divide pages roughly evenly.

### Issue: Prefix appears cut off
- **Solution**: Use shorter prefix (1-3 characters), or choose center/left alignment instead of right.

### Issue: Can't see interval field
- **Solution**: You must select "Reset every N pages" option to see the interval field.

---

## 📞 Getting Help

1. **Check the logs**: After bundle creation, check `logs/buntool_[SESSION_ID].log`
2. **Review settings**: Scroll down in the log to see "RECORD OF USER SETTINGS" section
3. **Verify inputs**: Make sure all custom numbering fields are filled correctly

---

## 💡 Pro Tips

1. **Test First**: Create a small test bundle (5-10 pages) before processing large documents
2. **Use Meaningful Prefixes**: "Ev" for Evidence, "WS" for Witness Statements, etc.
3. **Align with Physical Bundles**: If printing, match interval with physical tabs
4. **Document Your Choice**: Include your numbering scheme in cover letters
5. **Consistent Across Copies**: Generated bundles maintain numbering consistency

---

## ✅ Ready to Go!

You're all set! The custom alphanumeric numbering feature is ready to use. Select your style, configure your prefix and reset mode, and create your bundle!

**Questions?** Check USAGE_EXAMPLES.md for real-world scenarios.
