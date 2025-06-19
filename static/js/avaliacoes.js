// static/js/avaliacoes.js

document.addEventListener('DOMContentLoaded', function() {
    const avaliacaoModalEl = document.getElementById('avaliacaoModal');
    if (!avaliacaoModalEl) return;

    const avaliacaoModal = new bootstrap.Modal(avaliacaoModalEl);
    const avaliacaoForm = document.getElementById('formAvaliacao');
    const agendamentoIdInput = document.getElementById('agendamentoIdInput');
    const modalAlertPlaceholder = document.getElementById('avaliacaoModalAlertPlaceholder');

    // Abre o modal quando um botão "Avaliar" é clicado
    document.querySelectorAll('.btn-avaliar-consulta').forEach(button => {
        button.addEventListener('click', function() {
            const agendamentoId = this.dataset.agendamentoId;
            agendamentoIdInput.value = agendamentoId;
            // Limpa o formulário antes de mostrar
            avaliacaoForm.reset();
            modalAlertPlaceholder.innerHTML = '';
            avaliacaoModal.show();
        });
    });

    // Envia a avaliação para a API quando o formulário do modal é submetido
    if (avaliacaoForm) {
        avaliacaoForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const data = {
                agendamento_id: formData.get('agendamento_id'),
                nota: formData.get('nota'),
                comentario: formData.get('comentario')
            };

            if (!data.nota) {
                showAlert('Por favor, selecione uma nota (de 1 a 5 estrelas).', 'warning', 'avaliacaoModalAlertPlaceholder');
                return;
            }

            const url = this.action;
            const csrftoken = getCookie('csrftoken');

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json().then(resData => ({ ok: response.ok, status: response.status, data: resData })))
            .then(({ ok, status, data }) => {
                if (ok) {
                    avaliacaoModal.hide();
                    // Mostra a mensagem de sucesso na página principal
                    showAlert(data.data.message, 'success', 'alertPlaceholderGlobal');
                    // Esconde o botão de avaliação que acabou de ser usado
                    const btnUsado = document.querySelector(`.btn-avaliar-consulta[data-agendamento-id="${data.agendamento_id}"]`);
                    if(btnUsado) {
                        btnUsado.style.display = 'none';
                    }
                    window.location.reload(); // Recarrega a página para refletir a avaliação
                } else {
                    showAlert(data.message, 'danger', 'avaliacaoModalAlertPlaceholder');
                }
            })
            .catch(error => {
                showAlert('Ocorreu um erro de rede. Tente novamente.', 'danger', 'avaliacaoModalAlertPlaceholder');
                console.error('Erro:', error);
            });
        });
    }

    // Funções helper (podem ser movidas para um arquivo global no futuro)
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

    function showAlert(message, type, placeholderId, clearPrevious = true) {
        const placeholder = document.getElementById(placeholderId);
        if (placeholder) {
            if(clearPrevious) placeholder.innerHTML = '';
            placeholder.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show mt-2" role="alert">${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`;
        }
    }
});