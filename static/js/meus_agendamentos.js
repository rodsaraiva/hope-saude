// static/js/meus_agendamentos.js

document.addEventListener('DOMContentLoaded', function() {
    // Funções helper que também podem ser movidas para um arquivo JS global no futuro
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

    function showAlert(message, type, placeholderId = 'alertPlaceholderGlobal', clearPrevious = true) {
        const alertPlaceholder = document.getElementById(placeholderId);
        if (!alertPlaceholder) {
            console.error(`Placeholder de alerta '${placeholderId}' não encontrado.`);
            return;
        }
        if(clearPrevious) alertPlaceholder.innerHTML = '';
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
        alertPlaceholder.append(wrapper);
    }

    // Pega o container principal que agora guarda a URL da API como um data-attribute
    const container = document.getElementById('agendamentos-container');
    if (!container) return; // Sai se o container não for encontrado

    const salaUrlTemplate = container.dataset.salaUrlTemplate;
    if (!salaUrlTemplate) {
        console.error("URL template da página da sala não encontrada no data-attribute.");
        return;
    }

    const csrftoken = getCookie('csrftoken');
    const entrarConsultaButtons = document.querySelectorAll('.entrar-consulta-btn');

    entrarConsultaButtons.forEach(button => {
        button.addEventListener('click', function() {
            // A lógica agora é muito mais simples: apenas redirecionar.
            const agendamentoId = this.dataset.agendamentoId;
            const salaUrl = salaUrlTemplate.replace('0', agendamentoId.toString());
            
            // Mostra um estado de "carregando" no botão e redireciona
            this.disabled = true;
            this.innerHTML = '<span classs="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Entrando na sala...';
            
            window.location.href = salaUrl;
        });
    });

});