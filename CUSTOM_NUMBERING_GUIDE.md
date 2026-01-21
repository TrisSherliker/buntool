# Custom Alphanumeric Page Numbering Feature

## Overview
This feature adds support for custom alphanumeric page numbering to BunTool, allowing users to number pages with custom schemes like A1, A2, A3, B1, B2, etc.

## Implementation Details

### 1. Frontend Changes (`templates/index.html`)
- Added new page numbering style option: "Custom Alphanumeric e.g. 'A1', 'A2', 'B1'"
- Added three new form fields (conditionally visible):
  - **Custom numbering prefix**: Text input for the letter prefix (e.g., 'A', 'AB', 'Doc')
  - **Reset numbering**: Dropdown with three options:
    - Sequential (1, 2, 3, ...)
    - Change letter per 26 pages (A1-A26, B1-B26, ...)
    - Reset every N pages (custom interval)
  - **Reset every N pages**: Number input for the reset interval (default: 20)

### 2. JavaScript Logic (`static/buntool.js`)
- Added event listener to show/hide custom alpha configuration fields based on page numbering style selection
- When "Custom Alphanumeric" is selected, the custom configuration rows become visible
- When "Reset every N pages" is selected, the interval input becomes visible

### 3. Backend Logic (`bundle.py`)

#### New Function: `generate_custom_alpha_page_number()`
Located around line 785, this function generates custom alphanumeric page numbers:

```python
def generate_custom_alpha_page_number(page_number, prefix="", reset_mode="none", reset_interval=20)
```

**Parameters:**
- `page_number`: Current page number (1-indexed)
- `prefix`: Letter prefix (e.g., 'A', 'AB', 'Doc')
- `reset_mode`: One of "none", "letter_change", "custom"
- `reset_interval`: Pages before resetting counter

**Reset Modes:**
- **"none"**: Sequential numbering (1, 2, 3, ...) or with prefix (A1, A2, A3, ...)
- **"letter_change"**: Changes letter every 26 pages (A1-A26, B1-B26, AA1-AA26, ...)
- **"custom"**: Resets numbering every N pages with automatic letter increment (A1-A20, B1-B20, ...)

#### Updated: `BundleConfig` Class
Extended the constructor to include three new parameters:
- `custom_alpha_prefix`: Letter prefix for numbering
- `custom_alpha_reset`: Reset mode ("none", "letter_change", "custom")
- `custom_alpha_reset_interval`: Pages before reset (for custom mode)

#### Updated: `reportlab_footer_config()` Function
Added handling for "custom_alpha" page numbering style:
- Checks if page_numbering_style == "custom_alpha"
- Retrieves custom alpha settings from bundle_config
- Calls `generate_custom_alpha_page_number()` to generate the page number text

### 4. Form Handling (`app.py`)
- Extracts three new form parameters:
  - `custom_alpha_prefix`
  - `custom_alpha_reset`
  - `custom_alpha_reset_interval`
- Passes these to BundleConfig during instantiation
- Logs custom numbering settings in the bundle creation process

### 5. Logging Enhancement
Added logging output in the bundle creation process to record:
- Custom alpha prefix
- Reset mode
- Reset interval (if applicable)

## Usage Examples

### Example 1: Simple Sequential with Prefix
- Style: Custom Alphanumeric
- Prefix: "A"
- Reset: Sequential
- Result: A1, A2, A3, A4, A5, ...

### Example 2: Auto-Incrementing Letters Every 26 Pages
- Style: Custom Alphanumeric
- Prefix: (empty)
- Reset: Change letter per 26 pages
- Result: A1, A2, ..., A26, B1, B2, ..., B26, C1, ...

### Example 3: Reset Every 20 Pages
- Style: Custom Alphanumeric
- Prefix: "Section"
- Reset: Reset every N pages
- Interval: 20
- Result: Section A1, A2, ..., A20, B1, B2, ..., B20, ...

## Technical Notes

1. **Page Number Offset**: The function handles frontmatter offset automatically through the `length_of_frontmatter_offset` global variable in `reportlab_footer_config()`.

2. **Letter Generation**: For reset modes that cycle through letters, the implementation uses automatic letter generation:
   - 0-25: A-Z
   - 26-51: AA-AZ
   - 52-77: BA-BZ
   - And so on...

3. **Global Configuration**: Custom alpha settings are stored in the global `bundle_config` object, which is accessible to the footer configuration function.

4. **Backward Compatibility**: Existing numbering styles remain unchanged and functional. The custom numbering is purely additive.

## Files Modified

1. **templates/index.html**: Added UI for custom numbering configuration
2. **static/buntool.js**: Added event listeners for showing/hiding custom fields
3. **bundle.py**: 
   - Added `generate_custom_alpha_page_number()` function
   - Updated `BundleConfig` class
   - Updated `reportlab_footer_config()` function
   - Added logging for custom settings
4. **app.py**: Added form parameter extraction and BundleConfig instantiation

## Testing Recommendations

1. Test with empty prefix (should just show numbers)
2. Test with single letter prefix (e.g., "A" → A1, A2)
3. Test with multi-character prefix (e.g., "Doc" → Doc1, Doc2)
4. Test all three reset modes with various page counts
5. Verify page offsets are correct with coversheet/frontmatter
6. Test with different footer fonts and alignments
7. Check log output for custom numbering settings
