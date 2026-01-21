# PDF Numbering Tool - Quick Developer Reference

## 🚀 Quick Start

### Access the Tool
```
URL: http://localhost:7001/numbering_tool
```

### API Endpoint
```
POST /number_pdf
Content-Type: multipart/form-data

Returns: PDF file (application/pdf)
```

---

## 📝 Form Parameters

### Required
- `pdf_file` - File upload (PDF only, max 100 MB)

### Numbering Options
- `page_num_align` - "left" | "centre" | "right"
- `footer_font` - "sans" | "serif" | "mono" | "traditional"
- `page_num_style` - "x" | "x_of_y" | "x_slash_y" | "page_x" | "page_x_of_y" | "custom_alpha"

### Custom Alpha Options (if style = "custom_alpha")
- `custom_alpha_prefix` - Text prefix (e.g., "A", "Doc", "Section")
- `custom_alpha_reset` - "none" | "letter_change" | "custom"
- `custom_alpha_reset_interval` - Number of pages before reset (int)

### Page Range Mapping (optional)
- `use_page_range_mapping` - "on" | "off"
- `page_range_mapping_input` - CSV format: "1-20:A\n21-40:B\n41-60:C"

### Other Options
- `footer_prefix` - Optional text before page number (e.g., "Bundle pg")

---

## 🔧 Code Structure

### File Locations
```
/home/ojasai/bundler/buntool/
├── templates/
│   ├── numbering_tool.html          [NEW] Form UI
│   └── index.html                   [MODIFIED] Added link
├── static/
│   ├── numbering_tool.js            [NEW] Form behavior
│   └── buntool.css                  [EXISTING] Styling
├── app.py                           [MODIFIED] +2 routes, +160 lines
├── bundle.py                        [MODIFIED] +1 function, +100 lines
└── PDF_NUMBERING_TOOL.md           [NEW] Documentation
```

### Key Functions

#### Frontend
- `numbering_tool.html` - Form rendering
- `numbering_tool.js` - Form events and AJAX submission

#### Backend
- `app.numbering_tool()` - Route for GET /numbering_tool
- `app.number_pdf_route()` - Route for POST /number_pdf
- `bundle.number_single_pdf()` - Core numbering logic

---

## 💻 Integration Points

### How It Works

1. **User uploads PDF** → HTML file input
2. **User selects options** → Form fields
3. **User submits** → AJAX POST to /number_pdf
4. **Flask validates** → Check file, parameters
5. **Create config** → BundleConfig with numbering settings
6. **Process PDF** → number_single_pdf() function
7. **Generate numbers** → ReportLab generates blank page with numbers
8. **Overlay** → pypdf merges numbers onto original
9. **Return** → Stream PDF to browser
10. **Cleanup** → Delete temp files

### Reused Components

```python
# From bundle.py - already used by bundle tool
- generate_footer_pages_reportlab()      # Creates numbered pages
- add_footer_to_bundle()                 # Overlays numbers
- reportlab_footer_config()              # ReportLab callback
- generate_custom_alpha_page_number()    # Custom alpha logic
- parse_page_range_mapping()             # Parse range format
- get_custom_number_for_page_in_range()  # Lookup range
- BundleConfig class                     # Configuration object

# Flask utilities
- secure_filename()                      # Sanitize filenames
- tempfile                               # Temp directory
```

---

## 🧪 Testing

### Test File Upload
```bash
curl -F "pdf_file=@test.pdf" \
     -F "page_num_style=page_x" \
     -F "footer_font=sans" \
     -F "page_num_align=right" \
     http://localhost:7001/number_pdf \
     -o numbered.pdf
```

### Test Custom Alpha
```bash
curl -F "pdf_file=@test.pdf" \
     -F "page_num_style=custom_alpha" \
     -F "custom_alpha_prefix=A" \
     -F "custom_alpha_reset=sequential" \
     http://localhost:7001/number_pdf \
     -o numbered.pdf
```

### Test Page Range Mapping
```bash
curl -F "pdf_file=@test.pdf" \
     -F "page_num_style=custom_alpha" \
     -F "use_page_range_mapping=on" \
     -F "page_range_mapping_input=1-10:A\n11-20:B" \
     http://localhost:7001/number_pdf \
     -o numbered.pdf
```

---

## 📊 Form Field Dependencies

```
page_num_style === "custom_alpha"
  ├─ Show: custom_alpha_prefix
  ├─ Show: custom_alpha_reset
  └─ If custom_alpha_reset === "custom"
      └─ Show: custom_alpha_reset_interval

use_page_range_mapping === "on"
  └─ Show: page_range_mapping_input
```

---

## 🔍 Error Handling

### Validation Errors (400)
```json
{
  "status": "error",
  "message": "No PDF file provided"
}
```

### Processing Errors (500)
```json
{
  "status": "error",
  "message": "Error processing PDF: [details]"
}
```

### Logged Errors
- All errors logged to: `logs/numbering_[session_id].log`
- Check logs for debugging
- Session ID in response headers

---

## 🗂️ Temporary Files

### Location
```
/tmp/tempfiles/[session_id]/
├── [pdf_filename]                    (input)
├── pageNumbers_single.pdf            (generated numbers)
└── [pdf_filename]_numbered.pdf       (output)
```

### Cleanup
- All files deleted after response sent
- If cleanup fails, logged as warning
- System periodically flushes orphaned files

---

## 🚨 Logging

### Log Levels
```
DEBUG   - Detailed processing steps
INFO    - General flow, milestones
WARNING - Non-fatal issues
ERROR   - Fatal errors
```

### Log Location
```
logs/numbering_[session_id].log
```

### Log Format
```
[TIMESTAMP]-[LEVEL]-[NT]: [message]
```

### Key Log Points
```
[NT]Starting PDF numbering for [filename]
[NT]Input PDF has [N] pages
[NT]Generating page numbers PDF
[NT]Overlaying page numbers onto input PDF
[NT]Successfully created numbered PDF
[NT]Cleaned up temporary file
```

---

## 🔐 Security

### Input Validation
```python
# File type check
if not filename.lower().endswith('.pdf'):
    return error

# File size check (100 MB)
if file.content_length > app.config['MAX_CONTENT_LENGTH']:
    return error

# Filename sanitization
secure_name = secure_filename(file.filename)
```

### Directory Isolation
```python
# Temp dir per session
temp_dir = /tmp/tempfiles/[session_id]/

# No access outside temp dir
# Cleanup removes all files
```

---

## 📈 Performance Tips

### Optimization
1. ReportLab is very efficient (all time in overlay)
2. pypdf merging is the bottleneck (still fast)
3. For 100+ page PDFs, consider async processing

### Scaling
1. Add more worker threads (Waitress supports this)
2. Use dedicated temp drive (SSD recommended)
3. Monitor disk space for temp files
4. Increase file size limit if needed

### Monitoring
```bash
# Check temp directory size
du -sh /tmp/tempfiles/

# Check logs for errors
tail -f logs/numbering_*.log

# Check memory usage
watch ps aux | grep python
```

---

## 🔄 Request/Response Flow

### Request
```
POST /number_pdf HTTP/1.1
Content-Type: multipart/form-data

pdf_file: [binary PDF]
page_num_align: right
footer_font: sans
page_num_style: page_x
...
```

### Response Success (200)
```
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename="file_numbered.pdf"

[Binary PDF content]
```

### Response Error (400/500)
```
HTTP/1.1 400/500 Bad Request/Internal Server Error
Content-Type: application/json

{
  "status": "error",
  "message": "Error description"
}
```

---

## 🎯 Numbering Behavior

### Style: "x"
```
Input:  Page 1, 2, 3, ...
Output: 1, 2, 3, ...
```

### Style: "page_x"
```
Input:  Page 1, 2, 3, ...
Output: Page 1, Page 2, Page 3, ...
```

### Style: "page_x_of_y" (50 pages total)
```
Input:  Page 1, 2, 3, ..., 50
Output: Page 1 of 50, Page 2 of 50, ..., Page 50 of 50
```

### Style: "custom_alpha" + prefix "A" + reset "none"
```
Input:  Page 1, 2, 3, ...
Output: A1, A2, A3, ...
```

### Style: "custom_alpha" + prefix "" + reset "letter_change"
```
Input:  Page 1-26, 27-52, ...
Output: A1-A26, B1-B26, ...
```

### Style: "custom_alpha" + ranges ["1-10:A", "11-20:B"]
```
Input:  Page 1-10, 11-20, 21+
Output: A1-A10, B1-B10, 21+
```

---

## 🐛 Troubleshooting

### Problem: "File must be a PDF"
**Cause**: File extension not .pdf
**Solution**: Check file extension, rename if needed

### Problem: No error, no download
**Cause**: PDF processing failed, check logs
**Solution**: Check logs/numbering_*.log for details

### Problem: Page numbers look wrong
**Cause**: Font or alignment issue
**Solution**: Try different font, check alignment setting

### Problem: Custom alpha not working
**Cause**: Numbering style not set to custom_alpha
**Solution**: Verify page_num_style parameter

### Problem: Temp files not cleaned up
**Cause**: Cleanup failed (permissions, disk full)
**Solution**: Check logs, verify disk space, check permissions

---

## 🔗 Related Functions

### From bundle.py
```python
generate_footer_pages_reportlab(filename, num_pages)
# Creates blank PDF with page numbers via ReportLab

add_footer_to_bundle(input_file, page_numbers_pdf, output_file)
# Overlays numbered PDF onto original

reportlab_footer_config(canvas, doc)
# ReportLab callback that actually draws numbers

generate_custom_alpha_page_number(page_number, prefix, reset_mode, interval)
# Generates alphanumeric page numbers

parse_page_range_mapping(mapping_string)
# Parses range format: "1-20:A\n21-40:B"

get_custom_number_for_page_in_range(page_number, ranges)
# Looks up page in defined ranges
```

---

## 📚 Documentation Links

- **User Guide**: PDF_NUMBERING_TOOL.md
- **Implementation**: PDF_NUMBERING_TOOL_COMPLETE.md
- **Bundle Tool Docs**: README.md (existing)
- **API Reference**: This file

---

## ✅ Checklist for New Developers

- [ ] Read PDF_NUMBERING_TOOL.md
- [ ] Understand numbering_tool.html form
- [ ] Review numbering_tool.js event handlers
- [ ] Study number_single_pdf() function
- [ ] Understand BundleConfig usage
- [ ] Test file upload
- [ ] Test all numbering styles
- [ ] Test error handling
- [ ] Check logs location
- [ ] Review security considerations

---

**Last Updated**: January 21, 2026
**Version**: 1.0
**Status**: Production Ready ✅
