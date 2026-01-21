// Bookmark Tool JavaScript

let bookmarkCount = 0;

/**
 * Add a new bookmark entry to the form
 */
function addBookmark() {
    bookmarkCount++;
    const container = document.getElementById('bookmarksContainer');
    
    const bookmarkEntry = document.createElement('div');
    bookmarkEntry.className = 'bookmark-entry';
    bookmarkEntry.id = `bookmark-${bookmarkCount}`;
    bookmarkEntry.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div class="form-group">
                <label for="bookmark_title_${bookmarkCount}">Bookmark Title:</label>
                <input type="text" id="bookmark_title_${bookmarkCount}" 
                       name="bookmark_title_${bookmarkCount}" 
                       placeholder="e.g., Chapter 1, Introduction" required>
                <div class="help-text">The text that will appear in the bookmark list</div>
            </div>
            
            <div class="form-group">
                <label for="bookmark_page_${bookmarkCount}">Page Number:</label>
                <input type="number" id="bookmark_page_${bookmarkCount}" 
                       name="bookmark_page_${bookmarkCount}" 
                       min="1" placeholder="1" required>
                <div class="help-text">The page to link to (1-based)</div>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div class="form-group">
                <label for="bookmark_indent_${bookmarkCount}">Indent Level:</label>
                <select id="bookmark_indent_${bookmarkCount}" 
                        name="bookmark_indent_${bookmarkCount}">
                    <option value="0">Level 0 (Main)</option>
                    <option value="1">Level 1 (Sub-section)</option>
                    <option value="2">Level 2 (Sub-sub-section)</option>
                    <option value="3">Level 3 (Nested)</option>
                </select>
                <div class="indent-info">
                    Level 0 = Main bookmark<br>
                    Level 1+ = Nested under previous
                </div>
            </div>

            <div class="form-group">
                <label for="bookmark_style_${bookmarkCount}">Style:</label>
                <select id="bookmark_style_${bookmarkCount}" 
                        name="bookmark_style_${bookmarkCount}">
                    <option value="none">None</option>
                    <option value="bold">Bold</option>
                    <option value="italic">Italic</option>
                    <option value="bold_italic">Bold + Italic</option>
                </select>
            </div>
        </div>

        <button type="button" class="remove-bookmark" onclick="removeBookmark(${bookmarkCount})">
            Remove Bookmark
        </button>
    `;
    
    container.appendChild(bookmarkEntry);
}

/**
 * Remove a bookmark entry
 */
function removeBookmark(id) {
    const entry = document.getElementById(`bookmark-${id}`);
    if (entry) {
        entry.remove();
    }
}

/**
 * Show error modal
 */
function showErrorModal(message) {
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('errorModal').classList.add('show');
}

/**
 * Close error modal
 */
function closeErrorModal() {
    document.getElementById('errorModal').classList.remove('show');
}

/**
 * Toggle loader visibility
 */
function toggleLoader(show) {
    document.getElementById('loader').style.display = show ? 'block' : 'none';
    document.querySelector('.submit-btn').disabled = show;
}

/**
 * Handle form submission
 */
document.getElementById('bookmarkForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    // Validate file
    const fileInput = document.getElementById('pdf_file');
    if (!fileInput.files.length) {
        showErrorModal('Please select a PDF file');
        return;
    }
    
    // Validate bookmarks
    const bookmarks = document.querySelectorAll('.bookmark-entry');
    if (bookmarks.length === 0) {
        showErrorModal('Please add at least one bookmark');
        return;
    }
    
    // Collect bookmark data
    const bookmarkData = [];
    bookmarks.forEach((entry, index) => {
        const titleInput = entry.querySelector('input[id^="bookmark_title_"]');
        const pageInput = entry.querySelector('input[id^="bookmark_page_"]');
        const indentSelect = entry.querySelector('select[id^="bookmark_indent_"]');
        const styleSelect = entry.querySelector('select[id^="bookmark_style_"]');
        
        if (titleInput && pageInput && indentSelect && styleSelect) {
            const title = titleInput.value.trim();
            const page = parseInt(pageInput.value);
            
            if (!title) {
                showErrorModal(`Bookmark ${index + 1}: Title cannot be empty`);
                return false;
            }
            
            if (!page || page < 1) {
                showErrorModal(`Bookmark ${index + 1}: Page number must be at least 1`);
                return false;
            }
            
            bookmarkData.push({
                title: title,
                page: page,
                indent: parseInt(indentSelect.value),
                style: styleSelect.value
            });
        }
    });
    
    if (bookmarkData.length === 0) return;
    
    // Create form data
    const formData = new FormData();
    formData.append('pdf_file', fileInput.files[0]);
    formData.append('bookmark_color', document.getElementById('bookmark_color').value);
    formData.append('bookmark_bold', document.getElementById('bookmark_bold').checked ? 'on' : 'off');
    formData.append('bookmark_italic', document.getElementById('bookmark_italic').checked ? 'on' : 'off');
    formData.append('bookmarks_json', JSON.stringify(bookmarkData));
    
    // Show loader
    toggleLoader(true);
    
    try {
        const response = await fetch('/add_bookmarks', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            // Get the PDF blob and download it
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'document_with_bookmarks.pdf';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            
            alert('✅ PDF with bookmarks downloaded successfully!');
            // Reset form
            document.getElementById('bookmarkForm').reset();
            document.getElementById('bookmarksContainer').innerHTML = '';
            bookmarkCount = 0;
        } else {
            // Handle error response
            const errorData = await response.json();
            showErrorModal(errorData.message || 'Error processing PDF');
        }
    } catch (error) {
        console.error('Error:', error);
        showErrorModal(`Error: ${error.message}`);
    } finally {
        toggleLoader(false);
    }
});

/**
 * Initialize with one empty bookmark on page load
 */
window.addEventListener('DOMContentLoaded', function() {
    addBookmark();
});
