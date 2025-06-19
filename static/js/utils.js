// static/js/utils.js

/**
 * Obtém o valor de um cookie específico pelo nome.
 * Usado para pegar o CSRF token para requisições AJAX.
 * @param {string} name - O nome do cookie (ex: 'csrftoken').
 * @returns {string|null} O valor do cookie ou null.
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Exibe um alerta Bootstrap dinamicamente na página.
 * @param {string} message - A mensagem a ser exibida.
 * @param {string} type - O tipo do alerta ('success', 'danger', 'info', etc.).
 * @param {string} placeholderId - O ID do elemento onde o alerta será inserido.
 */
function showAlert(message, type, placeholderId = 'alertPlaceholderGlobal') {
    const placeholder = document.getElementById(placeholderId);
    if (placeholder) {
        const wrapper = document.createElement('div');
        let iconHtml = '';
        if (type === 'success') iconHtml = '<i class="bi bi-check-circle-fill me-2"></i>';
        else if (type === 'danger' || type === 'warning') iconHtml = '<i class="bi bi-exclamation-triangle-fill me-2"></i>';
        else if (type === 'info') iconHtml = '<i class="bi bi-info-circle-fill me-2"></i>';

        wrapper.innerHTML = [
            `<div class="alert alert-${type} alert-dismissible fade show mt-2" role="alert">`,
            `   <div>${iconHtml}${message}</div>`,
            '   <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>',
            '</div>'
        ].join('');
        // Limpa alertas anteriores antes de adicionar o novo
        placeholder.innerHTML = '';
        placeholder.append(wrapper);
    }
}