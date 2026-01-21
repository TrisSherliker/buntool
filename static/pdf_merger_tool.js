// PDF Merger Tool JavaScript

let files = []; // Array to store file objects with metadata
let draggedItem = null;

/**
 * Initialize file upload zone
 */
function initializeUploadZone() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');

    // Click to select files
    uploadZone.addEventListener('click', () => fileInput.click());

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });
}

/**
 * Handle file selection
 */
function handleFiles(selectedFiles) {
    for (let file of selectedFiles) {
        if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
            // Check if file already added
            if (!files.find(f => f.name === file.name && f.size === file.size)) {
                files.push({
                    file: file,
                    name: file.name,
                    size: file.size,
                    bookmark: '',
                    hasBookmark: false
                });
            }
        }
    }
    renderFileList();
}

/**
 * Render the file list
 */
function renderFileList() {
    const fileList = document.getElementById('fileList');

    if (files.length === 0) {
        fileList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📂</div>
                <p>No files selected yet. Upload files to begin.</p>
            </div>
        `;
        return;
    }

    fileList.innerHTML = files.map((fileObj, index) => `
        <div class="file-item" draggable="true" data-index="${index}">
            <div class="file-item-number">${index + 1}</div>
            <div class="file-item-content">
                <div class="file-item-name">📄 ${fileObj.name}</div>
                <div class="file-item-info">${formatFileSize(fileObj.size)}</div>
                ${fileObj.hasBookmark ? `<div class="file-item-info" style="color: #667eea; font-weight: 600;">🔖 Bookmark: "${fileObj.bookmark}"</div>` : ''}
            </div>
            <div class="file-item-controls">
                <button type="button" class="bookmark-toggle ${fileObj.hasBookmark ? 'active' : ''}" 
                        onclick="toggleBookmark(${index})">
                    ${fileObj.hasBookmark ? '🔖 Bookmark' : 'Add Bookmark'}
                </button>
                <button type="button" class="remove-file" onclick="removeFile(${index})">Remove</button>
            </div>
        </div>
        ${fileObj.hasBookmark ? `
            <div class="bookmark-labels show" data-index="${index}">
                <div class="bookmark-input">
                    <label>Bookmark Label:</label>
                    <input type="text" value="${fileObj.bookmark}" 
                           onchange="updateBookmarkLabel(${index}, this.value)"
                           placeholder="e.g., Chapter 1, Introduction, Appendix">
                </div>
            </div>
        ` : ''}
    `).join('');

    // Add drag event listeners
    addDragListeners();
}

/**
 * Toggle bookmark for a file
 */
function toggleBookmark(index) {
    files[index].hasBookmark = !files[index].hasBookmark;
    if (files[index].hasBookmark && !files[index].bookmark) {
        files[index].bookmark = files[index].name.replace('.pdf', '');
    }
    renderFileList();
}

/**
 * Update bookmark label
 */
function updateBookmarkLabel(index, value) {
    files[index].bookmark = value;
}

/**
 * Remove a file from the list
 */
function removeFile(index) {
    files.splice(index, 1);
    renderFileList();
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Add drag event listeners to file items
 */
function addDragListeners() {
    const fileItems = document.querySelectorAll('.file-item');

    fileItems.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            draggedItem = item;
            item.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
        });

        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            document.querySelectorAll('.file-item').forEach(el => {
                el.style.borderTop = 'none';
                el.style.opacity = '1';
            });
        });

        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            
            if (draggedItem && draggedItem !== item) {
                item.style.borderTop = '3px solid #667eea';
            }
        });

        item.addEventListener('dragleave', () => {
            item.style.borderTop = 'none';
        });

        item.addEventListener('drop', (e) => {
            e.preventDefault();
            item.style.borderTop = 'none';
            
            if (draggedItem && draggedItem !== item) {
                // Find indices by position in DOM
                const allItems = Array.from(document.querySelectorAll('.file-item'));
                const draggedIndex = allItems.indexOf(draggedItem);
                const targetIndex = allItems.indexOf(item);

                if (draggedIndex !== -1 && targetIndex !== -1 && draggedIndex !== targetIndex) {
                    // Swap in files array
                    [files[draggedIndex], files[targetIndex]] = [files[targetIndex], files[draggedIndex]];
                    renderFileList();
                }
            }
        });
    });
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
 * Toggle loader
 */
function toggleLoader(show) {
    document.getElementById('loader').style.display = show ? 'block' : 'none';
    document.querySelector('.submit-btn').disabled = show;
}

/**
 * Handle form submission
 */
document.getElementById('mergerForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    // Validate files
    if (files.length === 0) {
        showErrorModal('Please add at least one PDF file');
        return;
    }

    if (files.length === 1) {
        showErrorModal('Please add at least two PDF files to merge');
        return;
    }

    // Create FormData
    const formData = new FormData();

    // Add files in order
    files.forEach((fileObj, index) => {
        formData.append('files', fileObj.file);
        formData.append(`bookmark_${index}`, fileObj.hasBookmark ? fileObj.bookmark : '');
    });

    // Add output filename
    const outputFilename = document.getElementById('outputFilename').value || 'merged_document.pdf';
    formData.append('outputFilename', outputFilename);

    // Show loader
    toggleLoader(true);

    try {
        const response = await fetch('/merge_pdfs', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            // Get the PDF blob and download it
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = outputFilename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);

            alert('✅ PDFs merged successfully and downloaded!');
            
            // Reset form
            files = [];
            document.getElementById('mergerForm').reset();
            document.getElementById('fileInput').value = '';
            renderFileList();
        } else {
            const errorData = await response.json();
            showErrorModal(errorData.message || 'Error merging PDFs');
        }
    } catch (error) {
        console.error('Error:', error);
        showErrorModal(`Error: ${error.message}`);
    } finally {
        toggleLoader(false);
    }
});

/**
 * Initialize on page load
 */
window.addEventListener('DOMContentLoaded', function() {
    initializeUploadZone();
    renderFileList();
});
