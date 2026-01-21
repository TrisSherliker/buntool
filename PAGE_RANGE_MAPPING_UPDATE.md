# Page Range Mapping Enhancement

## Overview
Enhanced the **Page Range Mapping** feature in the PDF Numbering Tool to:
1. **Override all other numbering styles** when enabled
2. **Restart numbering at 1 for each range** (e.g., 1-20:A produces A1-A20, 21-40:B produces B1-B20)
3. **Disable other numbering options** when page range mapping is active
4. **Skip numbering for pages outside defined ranges**

## Changes Made

### 1. Backend (bundle.py)
**File**: `bundle.py`

**Function Modified**: `get_page_numbering_footer()`
- **Location**: Lines 1160-1185 (approximately)
- **Change**: Moved page range mapping check to execute **BEFORE** other numbering style checks
- **Behavior**:
  - When page range mapping is enabled, it now completely overrides all other styles
  - Pages within defined ranges get `{prefix}{number}` where number restarts at 1 per range
  - Pages outside defined ranges don't get numbered (no fallback)

**Key Code Logic**:
```python
# Check if page range mapping is enabled - if so, OVERRIDE all other numbering styles
if hasattr(bundle_config, 'page_range_mapping') and bundle_config.page_range_mapping:
    current_page = canvas.getPageNumber() + length_of_frontmatter_offset
    range_prefix, page_in_range = get_custom_number_for_page_in_range(current_page, bundle_config.page_range_mapping)
    
    if range_prefix is not None and page_in_range is not None:
        # Page is within a defined range - use the mapped prefix and numbering
        footer_data += f"{range_prefix}{page_in_range}"
    else:
        # Page is outside all defined ranges - no numbering for this page
        pass  # Don't add any numbering
elif page_numbering_style == "custom_alpha":
    # Use custom alphanumeric numbering (only if page range mapping is not enabled)
    ...
```

### 2. Frontend JavaScript (static/numbering_tool.js)
**File**: `static/numbering_tool.js`

**Function Enhanced**: Event listener for `use_page_range_mapping` checkbox
- **Change**: Added logic to disable/enable other numbering options based on checkbox state
- **Features**:
  - When **checked**: 
    - Disables the `page_num_style` dropdown
    - Hides all custom alpha configuration rows
    - Shows a visual warning indicator
  - When **unchecked**:
    - Re-enables the `page_num_style` dropdown
    - Removes the warning indicator
    - Re-shows custom alpha options if they were previously selected

**Key Code Logic**:
```javascript
usePageRangeMappingCheckbox.addEventListener('change', function() {
    if (this.checked) {
        // Page range mapping is enabled - disable other options
        pageRangeMappingRow.style.display = 'table-row';
        pageNumStyleSelect.disabled = true;
        pageNumStyleSelect.style.opacity = '0.5';
        // Hide custom alpha options...
        // Add visual warning indicator...
    } else {
        // Page range mapping is disabled - re-enable other options
        pageRangeMappingRow.style.display = 'none';
        pageNumStyleSelect.disabled = false;
        pageNumStyleSelect.style.opacity = '1';
        // Remove warning indicator...
        // Re-show custom alpha options if selected...
    }
});
```

### 3. Frontend HTML (templates/numbering_tool.html)
**File**: `templates/numbering_tool.html`

**Changes**: Enhanced the help text for page range mapping textarea
- Added warning: "⚠️ Page range mapping OVERRIDES all other numbering styles"
- Clarified that numbering restarts for each range
- Updated example descriptions to be more explicit about the restart behavior
- Added note: "Pages outside defined ranges will NOT be numbered"

**Updated Help Text**:
```
⚠️ Page range mapping OVERRIDES all other numbering styles
Format: start-end:prefix (numbering restarts for each range)
- Each line is one range
- Example: 1-20:A → pages numbered A1-A20
- Example: 21-40:B → pages numbered B1-B20 (restarts at B1)
- Pages outside defined ranges will NOT be numbered
- Can use different prefixes: 1-15:Doc, 16-30:Ev
```

## Behavior Changes

### Before
- Page range mapping was optional and only applied to custom_alpha numbering style
- Pages outside defined ranges would fall back to global custom alpha numbering
- Other numbering styles could be active simultaneously with page range mapping

### After
- Page range mapping **completely overrides** all other numbering styles
- When enabled, the page_num_style selector is disabled
- Each range restarts numbering from 1
- Example: 
  - Range 1-20:A → produces A1, A2, ..., A20
  - Range 21-40:B → produces B1, B2, ..., B20 (NOT B21, B22, ...)
  - Pages outside ranges (e.g., page 41+) → not numbered

### User Interface
- Visual warning indicator appears when page range mapping is enabled
- The numbering style dropdown becomes disabled (greyed out)
- Custom alpha configuration options are hidden
- Clear documentation explaining the override behavior

## Testing Example

### Input
```
1-20:A
21-40:B
```

### Output
- Pages 1-20: A1, A2, A3, ..., A20
- Pages 21-40: B1, B2, B3, ..., B20
- Pages 41+: No numbering (or continues with other style if re-enabled)

## Files Modified
1. ✅ `/home/ojasai/bundler/buntool/bundle.py` - Backend logic reordered
2. ✅ `/home/ojasai/bundler/buntool/static/numbering_tool.js` - Frontend UX enhancement
3. ✅ `/home/ojasai/bundler/buntool/templates/numbering_tool.html` - Help text updated

## Syntax Verification
- ✅ `bundle.py` - Python syntax verified
- ✅ `app.py` - Python syntax verified (imports bundle.py)
- ✅ `numbering_tool.js` - JavaScript syntax verified with Node.js
- ✅ `numbering_tool.html` - Valid HTML

## Backward Compatibility
✅ **Fully backward compatible**
- Existing functionality of custom_alpha numbering is preserved
- Page range mapping remains optional (checkbox disabled by default)
- Other numbering styles continue to work when page range mapping is not enabled

## Testing
To test the new behavior:
1. Navigate to `/numbering_tool`
2. Enable "Enable custom mapping for specific page ranges" checkbox
3. Notice that:
   - The numbering style selector becomes disabled
   - A warning indicator appears
   - Custom alpha options are hidden
4. Enter page ranges like:
   ```
   1-20:A
   21-30:B
   ```
5. Upload a PDF with at least 30 pages
6. Generate and verify that:
   - Pages 1-20 are numbered A1-A20
   - Pages 21-30 are numbered B1-B10 (not B21-B30)
