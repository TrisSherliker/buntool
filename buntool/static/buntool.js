import Sortable from 'sortablejs';
import * as pdfjsLib from 'pdfjs-dist';

import { filenameMappings, uploadedFiles } from './modules/state.js';
import {
    sanitizeFilename,
    prettifyTitle,
    escapeCsvField,
    parseDateFromFilename
} from './modules/utils.js';
import {
    showMessage,
    showError,
    showProcessMessage,
    showProcessError,
    showZipExplainer,
    clearProcessErrorMessages,
    clearZipExplainer,
    showDuplicateModal,
    closeDuplicateModal,
    clearCoversheet
} from './modules/ui.js';

// Initialize PDF.js - used for page counts
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://esm.sh/pdfjs-dist@4.0.379/build/pdf.worker.min.mjs';

// Initialize variables
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const progressBar = document.querySelector('.progress-bar');
const progressContainer = document.querySelector('.progress-container');
const bundleForm = document.getElementById('bundleForm');
const downloadButtonContainer = document.getElementById('downloadButtonContainer');
const downloadButton = document.getElementById('downloadButton');
const downloadZipButton = document.getElementById('downloadZipButton');
const loadingIndicator = document.getElementById('loadingIndicator');

// Initialize Sortable
new Sortable(fileList, {
    handle: '.drag-handle',
    animation: 150
});

// Event Listeners
// The click listener for dropZone has been removed as it was redundant. The <label> in the HTML now correctly handles opening the file dialog.

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});


const handleFiles = async (files) => {
    progressContainer.style.display = 'block';
    const totalFiles = files.length;
    let processedFiles = 0;
    let successful_uploads = 0;
    let unsuccessful_uploads = 0;

    for (let file of files) {
        if (file.type !== 'application/pdf') {
            showError(`${file.name} is not a PDF file`);
            continue;
        }

        if (uploadedFiles.has(file.name)) {
            showDuplicateModal(file.name);
            continue;
        }

        try {
            let extension = file.name.slice(file.name.lastIndexOf('.'));
            let baseName = file.name.slice(0, file.name.lastIndexOf('.'));
            let sanitizedBase = sanitizeFilename(baseName);
            let sanitizedName = baseName + extension;
            filenameMappings.set(file.name, sanitizedName);
            uploadedFiles.set(file.name, file); // Store the File object

            await processPDFFile(file, sanitizedName, baseName);
            processedFiles++;
            progressBar.style.width = `${(processedFiles / totalFiles) * 100}%`;
            successful_uploads++;
        } catch (error) {
            showError(`Error processing ${file.name}: ${error.message}`);
            unsuccessful_uploads++;
        }
    }

    if (successful_uploads > 0) {
        showMessage(`${successful_uploads} files uploaded successfully.`);
        document.getElementById('file-table').style.display = 'block'; // Make file-table visible
    }
    if (unsuccessful_uploads > 0)
        showError(`${unsuccessful_uploads} files failed to upload.`);

    setTimeout(() => {
        progressContainer.style.display = 'none';
        progressBar.style.width = '0';
    }, 1000);
}

const processPDFFile = async (file, sanitizedFileName, originalBasename) => {
    try {
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        const pageCount = pdf.numPages;

        addFileToList({
            originalName: file.name,
            sanitizedName: sanitizedFileName,
            title: prettifyTitle(originalBasename),
            date: new Date(file.lastModified).toISOString().split('T')[0],
            pages: pageCount
        });
    } catch (error) {
        throw new Error('Failed to process PDF file');
    }
}

const addFileToList = (fileData) => {
    console.log("Adding file to list:", fileData);
    const row = document.createElement('tr');
    const parsedResult = parseDateFromFilename(fileData.originalName, fileData.title);
    console.log("Parsed result:", parsedResult.date, parsedResult.titleWithoutDate);
    const dateToDisplay = parsedResult.date ?? fileData.date;
    const titleToDisplay = parsedResult.titleWithoutDate ?? fileData.title;

    // Escape double quotes to prevent breaking the HTML attribute
    const safeOriginalName = fileData.originalName.replace(/"/g, '&quot;');

    row.innerHTML = `
        <td><div class="drag-handle"><span style="background-color: #68b3cd; color: white; padding: 0.2rem 0.5rem; border-radius: 0.3rem;">☰</span></div></td>
        <td data-original-name="${safeOriginalName}">${fileData.sanitizedName}</td>
        <td><input type="text" value="${titleToDisplay}" class="w-full"></td>
        <td><input type="text" value="${dateToDisplay}" class="w-full"></td>
        <td>${fileData.pages}</td>
        <td><button type="button" class="remove-button">❌</button></td>
    `;
    fileList.appendChild(row);
}

const removeFile = (row, originalName) => {
    row.remove();
    uploadedFiles.delete(originalName);
    console.log(`Removed file: ${originalName}`);
}

const addSection = () => {
    const row = document.createElement('tr');
    row.className = 'section-row';
    row.innerHTML = `
        <td><div class="drag-handle"><span style="background-color: #68b3cd; color: white; padding: 0.2rem 0.5rem; border-radius: 0.3rem;">☰</span></div></td>
        <td colspan="4"><input type="text" placeholder="Enter Section Name e.g. Part 1: Pleadings [drag to position]" class="w-full"></td>
        <td><button type="button" class="remove-button">❌</button></td>
    `;
    fileList.appendChild(row);
    row.classList.add('flash');
    setTimeout(() => row.classList.remove('flash'), 500);
}


const generateCSVContent = () => {
    console.log("Generating CSV content");
    let csvContent = 'filename,title,date,section\n';
    let sectionCounter = 0;

    const rows = fileList.querySelectorAll('tr');
    console.log("Number of rows found:", rows.length);
    rows.forEach(row => {
        console.log("Processing row:", row);
        if (row.classList.contains('section-row')) {
            sectionCounter++;
            const sectionInput = row.querySelector('input');
            const title = sectionInput ? sectionInput.value.trim() : '';
            const prettifiedTitle = prettifyTitle(title);
            csvContent += `SECTION_BREAK_${sectionCounter},${escapeCsvField(prettifiedTitle)},,1\n`;
        } else {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 4) {
                // Use sanitized filename from the filenameMappings map
                const originalFilename = cells[1].getAttribute('data-original-name')
                const sanitizedFilename = filenameMappings.get(originalFilename) ?? originalFilename;
                const title = cells[2].querySelector('input')?.value.trim() ?? '';
                const date = cells[3].querySelector('input')?.value ?? '';
                const prettifiedTitle = prettifyTitle(title);
                csvContent += [
                    escapeCsvField(sanitizedFilename),
                    escapeCsvField(prettifiedTitle),
                    escapeCsvField(date),
                    '0' // File row section flag
                ].join(',') + '\n';
            }
        }
    });
    console.log("Final CSV content:", csvContent);
    return csvContent;
}

document.addEventListener('DOMContentLoaded', () => {
    const btnAddSection = document.getElementById('btnAddSection');
    if (btnAddSection) btnAddSection.addEventListener('click', addSection);

    const btnClearAll = document.getElementById('btnClearAll');
    if (btnClearAll) btnClearAll.addEventListener('click', clearAllFiles);

    const thSortTitle = document.getElementById('thSortTitle');
    if (thSortTitle) thSortTitle.addEventListener('click', () => sortTable(2));

    const thSortDate = document.getElementById('thSortDate');
    if (thSortDate) thSortDate.addEventListener('click', () => sortTable(3));

    const btnClearCoversheet = document.getElementById('btnClearCoversheet');
    if (btnClearCoversheet) btnClearCoversheet.addEventListener('click', clearCoversheet);

    const btnCloseModal = document.getElementById('btnCloseModal');
    if (btnCloseModal) btnCloseModal.addEventListener('click', closeDuplicateModal);

    // Event Delegation for Delete Buttons
    const fileList = document.getElementById('fileList');
    if (fileList) {
        fileList.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-button')) {
                const row = e.target.closest('tr');
                if (row.classList.contains('section-row')) {
                    row.remove();
                } else {
                    const nameCell = row.querySelector('td[data-original-name]');
                    if (nameCell) {
                        const originalName = nameCell.dataset.originalName;
                        removeFile(row, originalName);
                    }
                }
            }
        });
    }
})


bundleForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    clearProcessErrorMessages();
    clearZipExplainer();
    document.getElementById('downloadButtonContainer').style.display = 'none';
    document.getElementById('loadingIndicator').style.display = 'block';
    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonText = submitButton.innerHTML;
    submitButton.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Creating Bundle...';
    submitButton.disabled = true;
    loadingIndicator.style.display = 'block';

    const formData = new FormData(form);

    // Clear any existing 'files' entries before adding the sorted ones
    formData.delete('files');

    // Build the list of files to append using a more functional approach
    const filesToAppend = Array.from(fileList.querySelectorAll('tr'))
        .filter(row => !row.classList.contains('section-row'))
        .map(row => {
            const originalName = row.querySelector('td[data-original-name]').dataset.originalName;
            const file = uploadedFiles.get(originalName);
            const sanitizedName = filenameMappings.get(file?.name);
            if (file && sanitizedName) {
                return new File([file], sanitizedName, { type: file.type, lastModified: file.lastModified });
            }
            return null;
        })
        .filter(Boolean); // Filter out any null values from failed mappings

    // Append the collected files to formData
    filesToAppend.forEach(file => formData.append('files', file));

    // Generate and append the CSV file
    const csvContent = generateCSVContent();
    const csvBlob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8' });
    const csvFile = new File([csvBlob], 'index.csv', {
        type: 'text/csv',
        lastModified: new Date().getTime()
    });

    formData.delete('csv_index');
    formData.append('csv_index', csvFile, 'index.csv');


    try {
        const response = await fetch('/create_bundle', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success') {
            showProcessMessage('Bundle created successfully!', 'success');
            downloadButtonContainer.style.display = 'block';
            downloadButton.onclick = () => {
                window.location.href = `/download/bundle?path=${encodeURIComponent(data.bundle_path)}`;
            };
            downloadZipButton.onclick = () => {
                window.location.href = `/download/zip?path=${encodeURIComponent(data.zip_path)}`;
            };
            showZipExplainer('You can download just the PDF bundle, or you can download a Zip file. The Zip packages everything together for filing (and later editing), plus a separate draft index in Word (docx) format.')
        } else {
            throw new Error(data.message ?? 'Unknown error occurred');
        }
    } catch (error) {
        showProcessError(`Failed to create bundle: ${error.message}`);
    } finally {
        submitButton.innerHTML = originalButtonText;
        submitButton.disabled = false;
        loadingIndicator.style.display = 'none';
    }
});

const clearAllFiles = () => {
    fileList.innerHTML = '';
    fileInput.value = '';
    filenameMappings.clear();
    uploadedFiles.clear(); // Clear stored files
}

const sortTable = (columnIndex) => {
    const table = document.getElementById('fileList');
    const rows = Array.from(table.getElementsByTagName('tr'));
    const headers = document.querySelectorAll('th.sortable');
    const currentHeader = headers[columnIndex - 2]; // Adjust for first two non-sortable columns

    // Determine sort direction
    const isAsc = !currentHeader.classList.contains('asc');

    // Reset other headers
    headers.forEach(header => {
        header.classList.remove('asc', 'desc');
    });

    // Set current header sort direction
    currentHeader.classList.toggle('asc', isAsc);
    currentHeader.classList.toggle('desc', !isAsc);

    // Sort rows, excluding section rows
    const sortedRows = rows.sort((a, b) => {
        // Don't sort section rows
        if (a.classList.contains('section-row')) return -1;
        if (b.classList.contains('section-row')) return 1;

        const aValue = a.getElementsByTagName('td')[columnIndex].querySelector('input')?.value || '';
        const bValue = b.getElementsByTagName('td')[columnIndex].querySelector('input')?.value || '';

        if (columnIndex === 3) { // Date column
            // Parse dates (assuming YYYY-MM-DD format)
            const aDate = aValue ? new Date(aValue) : new Date(0);
            const bDate = bValue ? new Date(bValue) : new Date(0);
            return isAsc ? aDate - bDate : bDate - aDate;
        } else {
            // Regular string comparison
            return isAsc ?
                aValue.localeCompare(bValue) :
                bValue.localeCompare(aValue);
        }
    });

    // Reorder the table
    sortedRows.forEach(row => table.appendChild(row));
}
