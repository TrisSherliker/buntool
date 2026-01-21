# Page Range Mapping - Quick Reference

## 🎯 What Is It?

Map specific document page ranges to different custom numbering schemes. Instead of A1, A2, A3... for all pages, you get:
- Pages 1-20 → A1-A20
- Pages 21-40 → B1-B20 (restarts at B1, NOT B21!)
- Pages 41-60 → C1-C20 (restarts at C1, NOT C41!)

**⚠️ Important**: Page range mapping **COMPLETELY OVERRIDES** all other numbering styles when enabled. The numbering style selector becomes disabled.

---

## 🚀 How to Use (3 Steps)

### Step 1: Enable
```
☑ Enable custom mapping for specific page ranges
```

### Step 2: Define Ranges
```
Format: start-end:prefix
One per line

Example:
1-20:A
21-40:B
41-60:C
```

### Step 3: Create Bundle
Click "Create Bundle" → Done!

---

## 📋 Format Rules

```
Format:     start-end:prefix
Example:    1-20:A

Valid:
1-20:A           ✅
1-10:Pleadings   ✅
15-25:Evidence   ✅

Invalid:
1-20             ❌ (missing prefix)
20-1:A           ❌ (start > end)
1:20:A           ❌ (wrong format)
```

---

## 💡 Real Examples

### Legal Bundle
```
1-15:Pleadings
16-30:Evidence
31-40:Witness
41-50:Judgment

Pages:
Pleadings1-Pleadings15
Evidence1-Evidence15
Witness1-Witness10
Judgment1-Judgment10
```

### Tabbed Document (5 tabs × 20 pages)
```
1-20:A
21-40:B
41-60:C
61-80:D
81-100:E

Pages:
A1-A20 (Tab A)
B1-B20 (Tab B)
C1-C20 (Tab C)
D1-D20 (Tab D)
E1-E20 (Tab E)
```

### Multi-Section
```
1-10:Cover
11-25:Index
26-60:Docs
61-100:Analysis

Pages:
Cover1-Cover10
Index1-Index15
Docs1-Docs35
Analysis1-Analysis40
```

---

## ⚙️ Settings Order

**In UI:**
1. Select numbering style: **"Custom Alphanumeric"**
2. (Optional) Set global prefix/reset if needed
3. ☑ **Check:** "Enable custom mapping..."
4. **Enter:** Your page range mappings
5. Click "Create Bundle"

**Note**: Range mappings override global custom numbering settings.

---

## 🔍 What Happens When...

| Scenario | Result |
|----------|--------|
| Page in range 1-20:A | Shows A1-A20 |
| Page in range 21-40:B | Shows B1-B20 |
| Page not in any range | Falls back to global numbering |
| Overlapping ranges | First match wins |
| Invalid range format | Range skipped, warning in logs |

---

## ✅ Common Tasks

### Task: Print Physical Bundle with Tabs
```
Have: 100-page document, want 5 physical tabs

Solution:
1-20:Tab-A
21-40:Tab-B
41-60:Tab-C
61-80:Tab-D
81-100:Tab-E

Print: Tabs labeled A, B, C, D, E
Pages: Tab-A1 to Tab-A20, etc.
```

### Task: Separate Document Types
```
Have: Mix of pleadings, evidence, witness statements

Solution:
1-15:Pleading
16-40:Evidence
41-50:Witness

Result: Clear section markers in page numbers
```

### Task: Large Bundle with Clear Sections
```
Have: 300-page bundle, want 10 sections

Solution:
1-30:A
31-60:B
61-90:C
91-120:D
121-150:E
151-180:F
181-210:G
211-240:H
241-270:I
271-300:J

Result: Each section clearly marked
```

---

## 🎓 Advanced Tips

1. **Meaningful Prefixes**
   - Use short codes: "Pl" (Pleading), "Ev" (Evidence), "WS" (Witness)
   - Or full words: "Pleading", "Evidence", "Witness"

2. **Uneven Ranges**
   ```
   1-5:Cover
   6-25:Index
   26-100:Content
   ```
   Ranges don't need to be equal size!

3. **Any Order**
   ```
   41-60:C
   1-20:A
   21-40:B
   
   Auto-sorted to: A, B, C order
   ```

4. **Gap Handling**
   ```
   1-20:A
   30-40:B
   Pages 21-29: Use global numbering (fallback)
   ```

---

## 🐛 Troubleshooting

### Problem: Pages Not Showing Custom Numbers
**Check:**
1. Did you enable the checkbox? ☑
2. Are ranges valid format? `start-end:prefix`
3. Check logs for parsing errors

### Problem: Prefix Cut Off
**Fix:**
- Use shorter prefix (1-3 chars)
- Change alignment to CENTER or LEFT

### Problem: Wrong Prefix on Some Pages
**Check:**
1. Verify page numbers are in your ranges
2. Look for overlapping ranges
3. Check logs for warnings

---

## 📊 Comparison

**Before (Global Only):**
```
Config: Prefix="A", Mode=Sequential
All pages: A1, A2, A3, ..., A100
```

**After (With Range Mapping):**
```
Config:
1-25:Pleading
26-50:Evidence
51-100:Analysis

Result: Pleading1-25, Evidence1-25, Analysis1-50
```

---

## 🔐 Important Notes

✅ Works with all fonts and alignments
✅ Works with coversheet and roman numerals
✅ Unlimited number of ranges
✅ Ranges auto-sorted
✅ Overlaps handled gracefully
⚠️ Pages outside ranges fall back to global settings
⚠️ Format strictly: `start-end:prefix`

---

## 📞 Need Help?

1. **Can't enable the feature?**
   → Select "Custom Alphanumeric" numbering style first

2. **Ranges not parsing?**
   → Check format: `start-end:prefix` (exactly)

3. **Pages missing numbers?**
   → Verify range covers those page numbers

4. **Want to debug?**
   → Check logs: `logs/buntool_[SESSION_ID].log`
   → Search for "Page range mapping"

---

## 📌 Quick Syntax

```
Syntax:        start-end:prefix
Min example:   1-10:A
Full example:  1-20:Evidence
Multiple:      (one per line)
               1-20:A
               21-40:B
```

**Remember:** No spaces around the colon!

---

## 🎉 You're Ready!

1. ☑ Enable page range mapping
2. Enter your ranges (format: `start-end:prefix`)
3. Click "Create Bundle"
4. Done! Your PDF has custom page numbering per range.

See **PAGE_RANGE_MAPPING.md** for complete documentation.
