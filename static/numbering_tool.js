// Numbering Tool JavaScript
// Handles form interactions and submission for PDF numbering

document.addEventListener('DOMContentLoaded', function() {
    const pageNumStyleSelect = document.getElementById('page_num_style');
    const customAlphaResetSelect = document.getElementById('custom_alpha_reset');
    const usePageRangeMappingCheckbox = document.getElementById('use_page_range_mapping');
    const numberingForm = document.getElementById('numberingForm');
    const pdfFileInput = document.getElementById('pdf_file');

    // Show/hide custom alpha configuration rows based on numbering style
    pageNumStyleSelect.addEventListener('change', function() {
        const customAlphaConfigRow = document.getElementById('customAlphaConfigRow');
        const customAlphaResetRow = document.getElementById('customAlphaResetRow');
        const customAlphaResetIntervalRow = document.getElementById('customAlphaResetIntervalRow');
        
        if (this.value === 'custom_alpha') {
            customAlphaConfigRow.style.display = 'table-row';
            customAlphaResetRow.style.display = 'table-row';
            // Check if reset mode is set to custom
            if (customAlphaResetSelect.value === 'custom') {
                customAlphaResetIntervalRow.style.display = 'table-row';
            }
        } else {
            customAlphaConfigRow.style.display = 'none';
            customAlphaResetRow.style.display = 'none';
            customAlphaResetIntervalRow.style.display = 'none';
        }
    });

    // Show/hide reset interval row based on reset mode
    customAlphaResetSelect.addEventListener('change', function() {
        const customAlphaResetIntervalRow = document.getElementById('customAlphaResetIntervalRow');
        if (pageNumStyleSelect.value === 'custom_alpha' && this.value === 'custom') {
            customAlphaResetIntervalRow.style.display = 'table-row';
        } else {
            customAlphaResetIntervalRow.style.display = 'none';
        }
    });

    // Show/hide page range mapping textarea and disable other options
    usePageRangeMappingCheckbox.addEventListener('change', function() {
        const pageRangeMappingRow = document.getElementById('pageRangeMappingRow');
        const customAlphaConfigRow = document.getElementById('customAlphaConfigRow');
        const customAlphaResetRow = document.getElementById('customAlphaResetRow');
        const customAlphaResetIntervalRow = document.getElementById('customAlphaResetIntervalRow');
        
        if (this.checked) {
            // Page range mapping is enabled - show textarea and disable all other options
            pageRangeMappingRow.style.display = 'table-row';
            
            // Disable page numbering style selector
            pageNumStyleSelect.disabled = true;
            pageNumStyleSelect.style.opacity = '0.5';
            
            // Hide all custom alpha options
            customAlphaConfigRow.style.display = 'none';
            customAlphaResetRow.style.display = 'none';
            customAlphaResetIntervalRow.style.display = 'none';
            
            // Add visual indicator
            const indicator = document.createElement('div');
            indicator.id = 'pageRangeOverrideIndicator';
            indicator.style.cssText = 'color: #667eea; font-size: 0.9em; font-weight: bold; margin-top: 5px;';
            indicator.textContent = '⚠ Page range mapping will OVERRIDE other numbering styles';
            pageNumStyleSelect.parentElement.appendChild(indicator);
        } else {
            // Page range mapping is disabled - hide textarea and re-enable other options
            pageRangeMappingRow.style.display = 'none';
            
            // Re-enable page numbering style selector
            pageNumStyleSelect.disabled = false;
            pageNumStyleSelect.style.opacity = '1';
            
            // Remove visual indicator
            const indicator = document.getElementById('pageRangeOverrideIndicator');
            if (indicator) {
                indicator.remove();
            }
            
            // Re-show custom alpha options if currently selected
            if (pageNumStyleSelect.value === 'custom_alpha') {
                customAlphaConfigRow.style.display = 'table-row';
                customAlphaResetRow.style.display = 'table-row';
                if (customAlphaResetSelect.value === 'custom') {
                    customAlphaResetIntervalRow.style.display = 'table-row';
                }
            }
        }
    });

    // Handle form submission
    numberingForm.addEventListener('submit', function(e) {
        e.preventDefault();

        // Validate file input
        if (!pdfFileInput.files || pdfFileInput.files.length === 0) {
            showError('Please select a PDF file to number.');
            return;
        }

        // Create FormData object and submit
        const formData = new FormData(numberingForm);
        
        // Show loading state
        const submitButton = numberingForm.querySelector('button[type="submit"]');
        const originalText = submitButton.innerHTML;
        submitButton.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Processing...';
        submitButton.disabled = true;

        // Submit form via AJAX
        fetch('/number_pdf', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (response.ok) {
                return response.blob();
            } else if (response.status === 400 || response.status === 500) {
                return response.json().then(data => {
                    throw new Error(data.message || 'Error processing PDF');
                });
            } else {
                throw new Error('Unexpected error: ' + response.status);
            }
        })
        .then(blob => {
            // Download the PDF
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = pdfFileInput.files[0].name.replace('.pdf', '_numbered.pdf');
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            // Hide button container and show success message
            const downloadButtonContainer = document.getElementById('downloadButtonContainer');
            downloadButtonContainer.style.display = 'none';
            
            const processErrorContainer = document.getElementById('processErrorContainer');
            processErrorContainer.innerHTML = '<div style="background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 1rem; border-radius: 4px;"><strong>Success!</strong> Your PDF has been numbered and downloaded. You can process another file if needed.</div>';

            // Reset form for next upload
            setTimeout(() => {
                numberingForm.reset();
                processErrorContainer.innerHTML = '';
                submitButton.innerHTML = originalText;
                submitButton.disabled = false;
            }, 3000);
        })
        .catch(error => {
            console.error('Error:', error);
            submitButton.innerHTML = originalText;
            submitButton.disabled = false;
            showError(error.message || 'Failed to process PDF. Please try again.');
        });
    });
});

function showError(message) {
    const errorModal = document.getElementById('errorModal');
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    errorModal.style.display = 'flex';
}
