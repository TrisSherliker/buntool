export const showDuplicateModal = (filename) => {
    const modal = document.getElementById('duplicateModal');
    const message = document.getElementById('duplicateMessage');
    message.innerHTML = `<b>Duplicate file detected</b> <br><br> Did you mean to upload the file <i>'${filename}'</i> more than once?<br><br>Buntool has detected multiple copies of the same filename. This is usually a mistake, so BunTool will ignore the second copy for now. <br><br>If you do want to add the file twice, just make a copy of it with a different filename, and upload that.`;
    modal.style.display = 'flex';
}

export const closeDuplicateModal = () => {
    const modal = document.getElementById('duplicateModal');
    modal.style.display = 'none';
}

export const clearCoversheet = () => {
    const input = document.getElementById('coversheetInput');
    if (input) input.value = '';
}

export const clearCSVIndex = () => {
    const input = document.getElementById('csv_index');
    if (input) input.value = '';
}

export const showMessage = (message, type = 'success') => {
    const messageDiv = document.createElement('div');
    messageDiv.className = `success-message`;
    messageDiv.innerHTML = `<i class="mdi mdi-check-circle"></i>${message}`;
    document.getElementById('errorContainer').appendChild(messageDiv);
    setTimeout(() => messageDiv.remove(), 5000);
}

export const showError = (message) => {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `<i class="mdi mdi-alert-circle"></i>${message}`;
    document.getElementById('errorContainer').appendChild(errorDiv);
    setTimeout(() => errorDiv.remove(), 5000);
}

export const showProcessMessage = (message, type = 'success') => {
    const messageDiv = document.createElement('div');
    messageDiv.className = `success-message`;
    messageDiv.innerHTML = `<i class="mdi mdi-check-circle"></i>${message}`;
    document.getElementById('processErrorContainer').appendChild(messageDiv);
    setTimeout(() => messageDiv.remove(), 5000);
}

export const showProcessError = (message) => {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `<i class="mdi mdi-alert-circle"></i>${message}`;
    document.getElementById('processErrorContainer').appendChild(errorDiv);
}

export const showZipExplainer = (message, type = 'success') => {
    const messageDiv = document.createElement('div');
    messageDiv.className = `success-message`;
    messageDiv.innerHTML = `<i class="mdi mdi-check-circle"></i>${message}`;
    document.getElementById('zipExplainerContainer').appendChild(messageDiv);
}

export const clearProcessErrorMessages = () => {
    const processErrorContainer = document.getElementById('processErrorContainer');
    processErrorContainer.innerHTML = '';
}

export const clearZipExplainer = () => {
    const zipExplainerContainer = document.getElementById('zipExplainerContainer');
    zipExplainerContainer.innerHTML = '';
}
