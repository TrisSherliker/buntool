# Summary of Changes - Custom Alphanumeric Page Numbering

## Files Modified: 4
1. templates/index.html
2. static/buntool.js
3. bundle.py
4. app.py

---

## 1. templates/index.html

### Location: Lines 315-360 (approximately)

### Added:
- New page numbering style option: "Custom Alphanumeric e.g. 'A1', 'A2', 'B1'"
- Three new table rows with form inputs:
  - `customAlphaConfigRow`: Custom numbering prefix input
  - `customAlphaResetRow`: Reset mode selector (Sequential/Letter change/Custom interval)
  - `customAlphaResetIntervalRow`: Number input for interval

### New Form Fields:
- `id="custom_alpha_prefix"` - Text input for prefix
- `id="custom_alpha_reset"` - Dropdown for reset mode
- `id="custom_alpha_reset_interval"` - Number input for reset interval

---

## 2. static/buntool.js

### Location: Lines 50-84 (after fileInput event listener)

### Added:
- Event listener for `page_num_style` dropdown change
- Shows/hides custom alpha configuration rows based on selection
- Shows/hides interval field based on reset mode selection
- JavaScript logic:
  - When "custom_alpha" is selected: Show custom_alpha_prefix and custom_alpha_reset rows
  - When "custom_alpha_reset" === "custom": Show custom_alpha_reset_interval row

---

## 3. bundle.py

### Change 1: New Function `generate_custom_alpha_page_number()`
**Location: Lines 785-827** (before `reportlab_footer_config`)

```python
def generate_custom_alpha_page_number(page_number, prefix="", reset_mode="none", reset_interval=20):
    '''
    Generate custom alphanumeric page numbers like A1, A2, B1, B2, etc.
    '''
    # Handles three reset modes:
    # - "none": Sequential (1, 2, 3, ...)
    # - "letter_change": A1-A26, B1-B26, ... (auto-increment per 26 pages)
    # - "custom": A1-AN, B1-BN, ... (auto-increment per N pages)
```

### Change 2: Updated `BundleConfig` Class Constructor
**Location: Lines 1631-1636** (in __init__ parameters and body)

**Added parameters to constructor:**
```python
custom_alpha_prefix=None, 
custom_alpha_reset="none", 
custom_alpha_reset_interval=20
```

**Added to __init__ body:**
```python
self.custom_alpha_prefix = custom_alpha_prefix if custom_alpha_prefix else ""
self.custom_alpha_reset = custom_alpha_reset if custom_alpha_reset else "none"
self.custom_alpha_reset_interval = int(custom_alpha_reset_interval) if custom_alpha_reset_interval else 20
```

### Change 3: Updated `reportlab_footer_config()` Function
**Location: Lines 897-913** (in the page numbering style checks)

**Added:**
```python
if page_numbering_style == "custom_alpha":
    # Use custom alphanumeric numbering
    custom_prefix = bundle_config.custom_alpha_prefix if hasattr(bundle_config, 'custom_alpha_prefix') else ""
    custom_reset = bundle_config.custom_alpha_reset if hasattr(bundle_config, 'custom_alpha_reset') else "none"
    custom_interval = bundle_config.custom_alpha_reset_interval if hasattr(bundle_config, 'custom_alpha_reset_interval') else 20
    current_page = canvas.getPageNumber() + length_of_frontmatter_offset
    footer_data += generate_custom_alpha_page_number(
        current_page,
        prefix=custom_prefix,
        reset_mode=custom_reset,
        reset_interval=custom_interval
    )
elif page_numbering_style == "x":
    # ... existing code ...
```

### Change 4: Enhanced Logging in `create_bundle()`
**Location: Lines 1816-1821** (in the settings log section)

**Added:**
```python
if bundle_config.page_num_style == "custom_alpha":
    bundle_logger.info(f"....Custom alpha prefix: {bundle_config.custom_alpha_prefix}")
    bundle_logger.info(f"....Custom alpha reset mode: {bundle_config.custom_alpha_reset}")
    if bundle_config.custom_alpha_reset == "custom":
        bundle_logger.info(f"....Custom alpha reset interval: {bundle_config.custom_alpha_reset_interval} pages")
```

---

## 4. app.py

### Change 1: Extract Form Parameters
**Location: Lines 187-190** (after roman_for_preface extraction)

**Added:**
```python
custom_alpha_prefix = request.form.get('custom_alpha_prefix', '')
custom_alpha_reset = request.form.get('custom_alpha_reset', 'none')
custom_alpha_reset_interval = request.form.get('custom_alpha_reset_interval', '20')
```

### Change 2: Log Custom Parameters
**Location: Lines 293-296** (in the logging section)

**Added:**
```python
app.logger.info(f"........custom_alpha_prefix: {custom_alpha_prefix}")
app.logger.info(f"........custom_alpha_reset: {custom_alpha_reset}")
app.logger.info(f"........custom_alpha_reset_interval: {custom_alpha_reset_interval}")
```

### Change 3: Pass to BundleConfig
**Location: Lines 313-315** (in BundleConfig instantiation)

**Added parameters:**
```python
custom_alpha_prefix=custom_alpha_prefix,
custom_alpha_reset=custom_alpha_reset,
custom_alpha_reset_interval=custom_alpha_reset_interval
```

---

## Feature Behavior Summary

### Reset Modes:
1. **Sequential**: Numbers continue indefinitely (1, 2, 3, 100, 200, ...)
2. **Letter Change**: Letter increments every 26 pages (A1-A26, B1-B26, C1-C26, ...)
3. **Custom Interval**: Letter increments every N pages (A1-AN, B1-BN, ...)

### Prefix Handling:
- Empty prefix: Shows just numbers/letters (e.g., "A1", "B5")
- Single letter prefix: Combines with number (e.g., "AA1", "AB5")
- Multi-character prefix: Full text + number (e.g., "Doc1", "Section2")

### Integration Points:
- Works with all existing font options (serif, sans, mono, traditional)
- Works with all existing alignment options (left, center, right)
- Properly handles frontmatter offset (coversheet + TOC)
- Compatible with Roman numeral preface numbering
- Respects footer prefix option

---

## Testing Checklist

- [ ] Default behavior unchanged (existing numbering styles still work)
- [ ] Custom alpha form fields appear only when selected
- [ ] Interval field appears only when "custom" reset is selected
- [ ] Sequential mode works with empty and filled prefixes
- [ ] Letter-change mode cycles through letters correctly
- [ ] Custom interval mode increments letters at correct intervals
- [ ] Page offset is correct with frontmatter
- [ ] Custom numbering works with different fonts and alignments
- [ ] Logging shows custom numbering settings
- [ ] All existing features remain functional
