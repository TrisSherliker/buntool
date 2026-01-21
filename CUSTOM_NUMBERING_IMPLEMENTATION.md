# Custom Alphanumeric Numbering - Quick Reference

## How It Works

### Step 1: User Interface
The user selects "Custom Alphanumeric e.g. 'A1', 'A2', 'B1'" from the page numbering style dropdown.

This reveals three additional form fields:
```
┌─────────────────────────────────────────────┐
│ Custom numbering prefix:                    │
│ [____] (e.g., 'A' for 'A1', 'Doc' for 'Doc1')
│                                              │
│ Reset numbering:                            │
│ [▼] Sequential / Letter per 26 / Reset N   │
│                                              │
│ Reset every N pages:                        │
│ [20] (only shown when "Reset N" is selected)
└─────────────────────────────────────────────┘
```

### Step 2: Processing
When the user submits the form:
1. App.py extracts the three new parameters
2. Passes them to BundleConfig
3. BundleConfig stores them as instance variables
4. During PDF creation, reportlab_footer_config() retrieves these values
5. For each page, generate_custom_alpha_page_number() creates the formatted page number

### Step 3: Output Examples

**Configuration:** Prefix="A", Reset="Sequential"
```
Page 1: A1
Page 2: A2
Page 3: A3
...
Page 100: A100
```

**Configuration:** Prefix="", Reset="Letter per 26"
```
Page 1: A1
Page 2: A2
...
Page 26: A26
Page 27: B1
Page 28: B2
...
Page 52: B26
Page 53: C1
```

**Configuration:** Prefix="Doc", Reset="Every 20"
```
Page 1: DocA1
Page 2: DocA2
...
Page 20: DocA20
Page 21: DocB1
Page 22: DocB2
...
Page 40: DocB20
Page 41: DocC1
```

## Code Flow

```
templates/index.html
    ↓ (user selects custom numbering)
    ↓ (JavaScript shows/hides fields)
    ↓ (user submits form)
    ↓
app.py
    ├─ Extract: custom_alpha_prefix
    ├─ Extract: custom_alpha_reset
    ├─ Extract: custom_alpha_reset_interval
    ├─ Create BundleConfig with these params
    ↓
bundle.py::create_bundle()
    ├─ Load bundle_config
    ├─ Set global bundle_config
    ├─ Generate TOC, paginate, etc.
    ↓
bundle.py::pdf_paginator_reportlab()
    ├─ Generate pages with page numbers
    ├─ Call reportlab_footer_config for each page
    ↓
bundle.py::reportlab_footer_config()
    ├─ Check if page_numbering_style == "custom_alpha"
    ├─ Get custom_alpha_* from bundle_config
    ├─ Call generate_custom_alpha_page_number()
    ├─ Add formatted number to footer
    ↓
bundle.py::generate_custom_alpha_page_number()
    ├─ Apply prefix if provided
    ├─ Handle reset mode:
    │  ├─ "none": Simple sequential with prefix
    │  ├─ "letter_change": Auto-increment letter per 26 pages
    │  └─ "custom": Auto-increment letter per N pages
    └─ Return formatted string (e.g., "A1", "DocB5")
```

## Feature Highlights

✅ **No Prefix Needed**: Can use just letters (A1, A2) or just numbers (1, 2)
✅ **Auto-Letter Increment**: Automatically cycles through letters when needed
✅ **Flexible Reset**: Three different reset modes for different use cases
✅ **Seamless Integration**: Works with all existing features (fonts, alignment, etc.)
✅ **Frontmatter Aware**: Properly offsets page numbers with coversheets/roman numerals
✅ **Logged**: Custom settings recorded in bundle creation logs

## Configuration Parameters

| Parameter | Type | Default | Values |
|-----------|------|---------|--------|
| custom_alpha_prefix | string | "" | Any text (A, AB, Doc, etc.) |
| custom_alpha_reset | string | "none" | "none", "letter_change", "custom" |
| custom_alpha_reset_interval | int | 20 | 1-999 |

## Form Field Visibility Logic

```javascript
if (page_num_style === "custom_alpha") {
    Show custom_alpha_prefix field
    Show custom_alpha_reset field
    if (custom_alpha_reset === "custom") {
        Show custom_alpha_reset_interval field
    }
} else {
    Hide all custom fields
}
```
