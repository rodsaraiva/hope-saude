// static/js/calendario_profissional_interativo.js

console.log("DEBUG (JS File): Script calendario_profissional_interativo.js CARREGADO (Versão com Alerts)");

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
const csrftoken = getCookie('csrftoken');
console.log("DEBUG (JS File): CSRF token:", csrftoken ? "Obtido" : "NÃO OBTIDO");

function showAlert(message, type, placeholderId = 'alertPlaceholderGlobal', clearPrevious = true) {
    const alertPlaceholder = document.getElementById(placeholderId);
    if (alertPlaceholder) {
        if(clearPrevious) alertPlaceholder.innerHTML = '';
        const wrapper = document.createElement('div');
        wrapper.innerHTML = [`<div class="alert alert-${type} alert-dismissible fade show mt-2" role="alert">`,`   <div>${message}</div>`,`   <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`,`</div>`].join('');
        alertPlaceholder.append(wrapper);
        console.log(`DEBUG (JS File): Alerta exibido: ${type} - ${message} em ${placeholderId}`);
    } else { console.error(`DEBUG (JS File): Placeholder de alerta '${placeholderId}' não encontrado.`);}
}

function formatToDateTimeLocalString(dateObj) {
    if (!dateObj) return '';
    const localDate = new Date(dateObj.getTime() - (dateObj.getTimezoneOffset() * 60000));
    return localDate.toISOString().slice(0, 16);
}

document.addEventListener('DOMContentLoaded', function() {
    console.log("DEBUG (JS File): DOMContentLoaded disparado.");

    const calendarDivForData = document.getElementById('calendar');
    if (!calendarDivForData) { 
        console.error("DEBUG (JS File): Div 'calendar' (para data-attributes) NÃO encontrado."); 
        showAlert("Erro crítico: Configuração do calendário ausente (div principal).", "danger");
        return;
    }
    console.log("DEBUG (JS File): Div 'calendar' (para data-attributes) ENCONTRADO.");

    const urlApiCriarDispAvulsa = calendarDivForData.dataset.urlApiCriarDispAvulsa;
    const urlApiEditarRegraBase = calendarDivForData.dataset.urlApiEditarRegraBase;
    const urlApiExcluirRegrasLista = calendarDivForData.dataset.urlApiExcluirRegrasLista;
    
    console.log("DEBUG (JS File): URL Criar Disp Avulsa:", urlApiCriarDispAvulsa);
    console.log("DEBUG (JS File): URL Base Editar Regra:", urlApiEditarRegraBase); // Ex: /contas/api/regras-disponibilidade/editar/0/
    console.log("DEBUG (JS File): URL Excluir Lista Regras:", urlApiExcluirRegrasLista);

    if (!urlApiCriarDispAvulsa || !urlApiEditarRegraBase || !urlApiExcluirRegrasLista) {
        console.error("DEBUG (JS File): Uma ou mais URLs de API não foram encontradas nos data-attributes!");
        showAlert("Erro crítico: URLs de API ausentes.", "danger");
    }

    const eventsDataElement = document.getElementById('calendar-events-data');
    if (!eventsDataElement) { console.error("DEBUG (JS File): Elem 'calendar-events-data' não encontrado."); showAlert("Erro crítico: dados de eventos não encontrados.", "danger"); return; }
    
    let calendarEvents = [];
    try {
        const parsedData = JSON.parse(eventsDataElement.textContent);
        if (Array.isArray(parsedData)) { calendarEvents = parsedData; } 
        else { console.error("DEBUG (JS File): Dados NÃO são Array! Tipo:", typeof parsedData); }
        console.log("DEBUG (JS File): Eventos iniciais para calendário:", calendarEvents.length);
    } catch (e) { console.error("DEBUG (JS File): Erro JSON.parse:", e); showAlert("Erro crítico ao processar dados de eventos.", "danger"); return; }

    const calendarEl = document.getElementById('calendar'); // Já verificado, mas pegamos de novo
    
    let calendarInstance; 
    let dispAvulsaModalInstance;
    let editarDispEspecificaModalInstance; 

    var dispAvulsaModalEl = document.getElementById('dispAvulsaModal');
    if (dispAvulsaModalEl) {
        dispAvulsaModalInstance = new bootstrap.Modal(dispAvulsaModalEl);
        console.log("DEBUG (JS File): Instância do dispAvulsaModal (adicionar) criada.");
    } else { console.error("DEBUG (JS File): HTML do Modal 'dispAvulsaModal' NÃO encontrado!"); }

    var editarDispEspecificaModalEl = document.getElementById('editarDispEspecificaModal');
    if (editarDispEspecificaModalEl) {
        editarDispEspecificaModalInstance = new bootstrap.Modal(editarDispEspecificaModalEl);
        console.log("DEBUG (JS File): Instância do editarDispEspecificaModal (editar/excluir) criada.");
    } else { console.error("DEBUG (JS File): HTML do Modal 'editarDispEspecificaModal' NÃO encontrado!"); }

    try {
        calendarInstance = new FullCalendar.Calendar(calendarEl, {
            initialView: 'timeGridWeek',
            headerToolbar: { left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek' },
            locale: 'pt-br', buttonText: { today: 'Hoje', month: 'Mês', week: 'Semana', day: 'Dia', list: 'Lista' },
            allDaySlot: false, slotMinTime: "07:00:00", slotMaxTime: "21:00:00",
            businessHours: { daysOfWeek: [ 1, 2, 3, 4, 5 ], startTime: '08:00', endTime: '18:00' },
            nowIndicator: true, expandRows: true, handleWindowResize: true, height: 'auto',
            navLinks: true, editable: true, selectable: true, selectMirror: true, unselectAuto: true,
            selectOverlap: function(eventExisting) { return eventExisting.display === 'background'; },
            events: function(info, successCallback, failureCallback) {
                // Função para carregar eventos dinamicamente
                fetch(window.location.href)
                    .then(response => response.text())
                    .then(html => {
                        // Extrair os dados do HTML retornado
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const eventsDataElement = doc.getElementById('calendar-events-data');
                        
                        if (eventsDataElement) {
                            try {
                                const parsedData = JSON.parse(eventsDataElement.textContent);
                                if (Array.isArray(parsedData)) {
                                    successCallback(parsedData);
                                } else {
                                    successCallback([]);
                                }
                            } catch (e) {
                                console.error("Erro ao processar eventos:", e);
                                successCallback([]);
                            }
                        } else {
                            successCallback([]);
                        }
                    })
                    .catch(error => {
                        console.error("Erro ao carregar eventos:", error);
                        failureCallback(error);
                    });
            },
            eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
            eventDidMount: function(info) { 
                if (info.event.title && info.el) { 
                    info.el.setAttribute('title', info.event.title); 
                }
                
                // Aplicar atributos de dados para estilização CSS
                if (info.event.extendedProps && info.event.extendedProps.tipo) {
                    info.el.setAttribute('data-event-type', info.event.extendedProps.tipo);
                }
                
                if (info.event.extendedProps && info.event.extendedProps.status) {
                    info.el.setAttribute('data-status', info.event.extendedProps.status);
                }
                
                // Adicionar classes CSS específicas baseadas no tipo de evento
                if (info.event.extendedProps && info.event.extendedProps.tipo) {
                    const eventType = info.event.extendedProps.tipo;
                    if (eventType === 'disponibilidade_semanal' || 
                        eventType === 'disponibilidade_especifica' || 
                        eventType === 'disponibilidade_especifica_agrupada') {
                        info.el.classList.add('fc-event-disponibilidade');
                    } else if (eventType === 'agendamento') {
                        info.el.classList.add('fc-event-agendamento');
                    }
                }
            },
            select: function(selectionInfo) {
                console.log('DEBUG (JS File): Período selecionado (select):', selectionInfo.start.toISOString(), 'a', selectionInfo.end.toISOString());
                if (!dispAvulsaModalInstance) {console.error("DEBUG (JS File): dispAvulsaModalInstance não definida no callback select!"); return;}
                document.getElementById('dispAvulsaModalAlertPlaceholder').innerHTML = ''; 
                const options = { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' };
                document.getElementById('dispAvulsaModalInfoInicio').textContent = selectionInfo.start.toLocaleString('pt-BR', options);
                document.getElementById('dispAvulsaModalInfoFim').textContent = selectionInfo.end.toLocaleString('pt-BR', options);
                document.getElementById('dispAvulsaModalStartTimeISO').value = selectionInfo.start.toISOString();
                document.getElementById('dispAvulsaModalEndTimeISO').value = selectionInfo.end.toISOString();
                dispAvulsaModalInstance.show();
                if (calendarInstance) { calendarInstance.unselect(); }
            },
            eventClick: function(info) {
                console.log('DEBUG (JS File): Evento clicado:', info.event.title, info.event.extendedProps);
                document.getElementById('alertPlaceholderGlobal').innerHTML = ''; 
                const eventType = info.event.extendedProps.tipo;
                let originalId = info.event.extendedProps.id_original;
                const idsOriginaisAgrupados = info.event.extendedProps.ids_originais; 
                console.log("DEBUG (JS File): eventClick - Tipo:", eventType, "ID Principal:", originalId, "IDs Agrupados:", idsOriginaisAgrupados);
                if ((eventType === 'disponibilidade_especifica' || eventType === 'disponibilidade_especifica_agrupada') && editarDispEspecificaModalInstance) {
                   let idParaEdicaoDoModal = null; let idsParaExclusaoDoModal = [];
                   if (eventType === 'disponibilidade_especifica_agrupada' && idsOriginaisAgrupados && idsOriginaisAgrupados.length > 0) { idParaEdicaoDoModal = idsOriginaisAgrupados[0]; idsParaExclusaoDoModal = idsOriginaisAgrupados; } 
                   else if (originalId) { idParaEdicaoDoModal = originalId; idsParaExclusaoDoModal = [originalId]; } 
                   else { console.error("DEBUG (JS File): ID original não encontrado."); return; }
                   console.log("DEBUG (JS File): Abrindo modal EDIÇÃO/EXCLUSÃO. ID Edição:", idParaEdicaoDoModal, "IDs Exclusão:", idsParaExclusaoDoModal);
                   document.getElementById('editarDispEspecificaId').value = idParaEdicaoDoModal;
                   document.getElementById('editarDispEspecificaAgrupadaIds').value = JSON.stringify(idsParaExclusaoDoModal);
                   document.getElementById('editarDispEspecificaStartTime').value = formatToDateTimeLocalString(info.event.start);
                   document.getElementById('editarDispEspecificaEndTime').value = info.event.end ? formatToDateTimeLocalString(info.event.end) : formatToDateTimeLocalString(new Date(info.event.start.getTime() + 3600000));
                   document.getElementById('editarDispEspecificaModalAlertPlaceholder').innerHTML = '';
                   editarDispEspecificaModalInstance.show();
                } else { 
                    let infoMsg = `Evento: ${info.event.title}`;
                    if(info.event.extendedProps && info.event.extendedProps.status) infoMsg += ` (Status: ${info.event.extendedProps.status})`;
                    else if(eventType === 'disponibilidade_semanal') infoMsg = "Disponibilidade Semanal. Para gerenciar, use 'Gerenciar Disponibilidade'.";
                    showAlert(infoMsg.replace(/\n/g, "<br>"), 'info', 'alertPlaceholderGlobal', true);
                    console.log("DEBUG (JS File): eventClick - Tipo não aciona modal de edição/exclusão.");
                }
            },
            eventDrop: function(dropInfo) { /* ... (lógica do eventDrop como na Resposta #151) ... */ }
        });
        calendarInstance.render();
        console.log("DEBUG (JS File): Calendário renderizado.");

        // --- HANDLER PARA ADICIONAR Disp. Avulsa (do dispAvulsaModal) ---
        const salvarDispAvulsaBtn = document.getElementById('salvarDispAvulsaBtn');
        if (salvarDispAvulsaBtn) {
            console.log("DEBUG (JS File): Botão 'salvarDispAvulsaBtn' ENCONTRADO. Anexando listener.");
            salvarDispAvulsaBtn.addEventListener('click', function() {
                console.log("DEBUG (JS File): Botão 'salvarDispAvulsaBtn' CLICADO!");
                
                // Mostrar indicador de carregamento
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="bi bi-hourglass-split"></i> Salvando...';
                this.disabled = true;
                
                const startTimeStr = document.getElementById('dispAvulsaModalStartTimeISO').value;
                const endTimeStr = document.getElementById('dispAvulsaModalEndTimeISO').value;
                const payload = { data_hora_inicio_especifica: startTimeStr, data_hora_fim_especifica: endTimeStr };
                document.getElementById('dispAvulsaModalAlertPlaceholder').innerHTML = '';
                console.log("DEBUG (JS File): Enviando para API (salvarDispAvulsaBtn):", urlApiCriarDispAvulsa, "Payload:", payload);
                if (!urlApiCriarDispAvulsa) { console.error("URL para criar disp avulsa não definida!"); return;}
                fetch(urlApiCriarDispAvulsa, {
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                    body: JSON.stringify(payload)
                })
                .then(response => { 
                    console.log("DEBUG (JS File): Resposta API (salvarDispAvulsaBtn) status:", response.status);
                    if (!response.ok) { return response.json().then(err => { throw new Error(err.message || `Erro ${response.status}`); }); }
                    return response.json();
                })
                .then(data => {
                    console.log("DEBUG (JS File): Dados API (salvarDispAvulsaBtn) sucesso:", data);
                    if(data.status==='success'){
                        showAlert(data.message||"Disponibilidade adicionada com sucesso!", "success", "alertPlaceholderGlobal", false);
                        if(calendarInstance) {
                            calendarInstance.refetchEvents();
                        }
                        if(dispAvulsaModalInstance) {
                            dispAvulsaModalInstance.hide();
                        }
                    } else {
                        showAlert('Erro: '+ (data.message || 'Desconhecido'), "danger", "dispAvulsaModalAlertPlaceholder");
                    }
                })
                .catch(e => {
                    console.error('Erro AJAX (salvarDispAvulsaBtn):',e); 
                    showAlert('Erro: '+e.message, "danger", "dispAvulsaModalAlertPlaceholder");
                })
                .finally(() => {
                    // Restaurar botão
                    this.innerHTML = originalText;
                    this.disabled = false;
                });
            });
            console.log("DEBUG (JS File): Listener para 'salvarDispAvulsaBtn' ANEXADO.");
        } else { console.error("DEBUG (JS File): Botão 'salvarDispAvulsaBtn' NÃO encontrado!");}

        // --- HANDLER PARA SALVAR EDIÇÃO de Disp. Específica (do editarDispEspecificaModal) ---
        const salvarEdicaoDispEspecificaBtn = document.getElementById('salvarEdicaoDispEspecificaBtn');
        if (salvarEdicaoDispEspecificaBtn) {
            console.log("DEBUG (JS File): Botão 'salvarEdicaoDispEspecificaBtn' ENCONTRADO. Anexando listener.");
            salvarEdicaoDispEspecificaBtn.addEventListener('click', function() {
                console.log("DEBUG (JS File): Botão 'salvarEdicaoDispEspecificaBtn' CLICADO!");
                
                // Mostrar indicador de carregamento
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="bi bi-hourglass-split"></i> Salvando...';
                this.disabled = true;
                
                const regraId = document.getElementById('editarDispEspecificaId').value;
                const startTimeFormValue = document.getElementById('editarDispEspecificaStartTime').value;
                const endTimeFormValue = document.getElementById('editarDispEspecificaEndTime').value;
                document.getElementById('editarDispEspecificaModalAlertPlaceholder').innerHTML = '';
                if (!regraId || !startTimeFormValue || !endTimeFormValue) { 
                    showAlert("ID, início e fim são obrigatórios.", "warning", "editarDispEspecificaModalAlertPlaceholder"); 
                    this.innerHTML = originalText;
                    this.disabled = false;
                    return; 
                }
                const startTimeISO = new Date(startTimeFormValue).toISOString();
                const endTimeISO = new Date(endTimeFormValue).toISOString();
                if (!urlApiEditarRegraBase) { console.error("URL base para editar regra não definida!"); return;}
                const apiUrl = urlApiEditarRegraBase.replace('0', regraId);
                console.log("DEBUG (JS File): Enviando para API (salvarEdicao):", apiUrl, {data_hora_inicio_especifica: startTimeISO, data_hora_fim_especifica: endTimeISO});
                fetch(apiUrl, {
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                    body: JSON.stringify({ data_hora_inicio_especifica: startTimeISO, data_hora_fim_especifica: endTimeISO })
                })
                .then(r => { console.log("DEBUG (JS File): Resposta API (Editar) status:", r.status); if(!r.ok){return r.json().then(eD => {throw new Error(eD.message||'Erro servidor')})} return r.json()})
                .then(d => { 
                    console.log("DEBUG (JS File): Dados API (Editar) sucesso:", d); 
                    if(d.status==='success'){ 
                        showAlert(d.message||"Disponibilidade atualizada com sucesso!", "success", "alertPlaceholderGlobal", false); 
                        if(calendarInstance) {
                            calendarInstance.refetchEvents();
                        }
                        if(editarDispEspecificaModalInstance) {
                            editarDispEspecificaModalInstance.hide();
                        }
                    } else {
                        showAlert('Erro: '+d.message, "danger", "editarDispEspecificaModalAlertPlaceholder");
                    }
                })
                .catch(e => {
                    console.error('Erro AJAX Editar Disp Específica:',e); 
                    showAlert('Erro: '+e.message, "danger", "editarDispEspecificaModalAlertPlaceholder");
                })
                .finally(() => {
                    // Restaurar botão
                    this.innerHTML = originalText;
                    this.disabled = false;
                });
            });
            console.log("DEBUG (JS File): Listener para 'salvarEdicaoDispEspecificaBtn' ANEXADO.");
        } else { console.error("DEBUG (JS File): Botão 'salvarEdicaoDispEspecificaBtn' NÃO encontrado!");}

        // --- HANDLER PARA EXCLUIR Disp. Específica (do editarDispEspecificaModal) ---
        const excluirDispEspecificaDoModalBtn = document.getElementById('excluirDispEspecificaDoModalBtn');
        if (excluirDispEspecificaDoModalBtn) {
            console.log("DEBUG (JS File): Botão 'excluirDispEspecificaDoModalBtn' ENCONTRADO. Anexando listener.");
            excluirDispEspecificaDoModalBtn.addEventListener('click', function() {
                console.log("DEBUG (JS File): Botão 'excluirDispEspecificaDoModalBtn' CLICADO!");
                
                const idsJson = document.getElementById('editarDispEspecificaAgrupadaIds').value;
                document.getElementById('editarDispEspecificaModalAlertPlaceholder').innerHTML = '';
                if (!idsJson) { showAlert("IDs não encontrados.", "danger", "editarDispEspecificaModalAlertPlaceholder"); return; }
                let idsParaExcluir = [];
                try { idsParaExcluir = JSON.parse(idsJson); } 
                catch(e) { console.error("Erro parse idsParaExcluir:", e); showAlert("Erro (IDs).", "danger","editarDispEspecificaModalAlertPlaceholder"); return;}
                if (!Array.isArray(idsParaExcluir) || idsParaExcluir.length === 0) { showAlert("Nenhuma disp. para exclusão.", "warning", "editarDispEspecificaModalAlertPlaceholder"); return; }
                const confirmMessage = idsParaExcluir.length > 1 ? `Excluir este bloco (afeta ${idsParaExcluir.length} regras)?` : `Excluir esta disponibilidade?`;
                if (confirm(confirmMessage)) {
                    // Mostrar indicador de carregamento
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="bi bi-hourglass-split"></i> Excluindo...';
                    this.disabled = true;
                    
                    if(!urlApiExcluirRegrasLista) { console.error("URL para excluir lista não definida!"); return; }
                    const apiUrl = urlApiExcluirRegrasLista; 
                    console.log("DEBUG (JS File): Enviando para API (Excluir Lista):", apiUrl, {ids: idsParaExcluir});
                    fetch(apiUrl, { 
                        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                        body: JSON.stringify({ ids: idsParaExcluir })
                    })
                    .then(r => {if(!r.ok){return r.json().then(eD => {throw new Error(eD.message||'Erro servidor')})} return r.json()})
                    .then(d => { 
                        if(d.status==='success'){ 
                            showAlert(d.message||"Disponibilidade excluída com sucesso!", "success", "alertPlaceholderGlobal", false); 
                            if(calendarInstance) {
                                calendarInstance.refetchEvents();
                            }
                            if(editarDispEspecificaModalInstance) {
                                editarDispEspecificaModalInstance.hide();
                            }
                        } else {
                            showAlert('Erro: '+d.message,"danger", "editarDispEspecificaModalAlertPlaceholder");
                        }
                    })
                    .catch(e => {
                        console.error('Erro AJAX Excluir Grupo Disp Específica:',e); 
                        showAlert('Erro: '+e.message, "danger", "editarDispEspecificaModalAlertPlaceholder");
                    })
                    .finally(() => {
                        // Restaurar botão
                        this.innerHTML = originalText;
                        this.disabled = false;
                    });
                }
            });
            console.log("DEBUG (JS File): Listener para 'excluirDispEspecificaDoModalBtn' ANEXADO.");
        }  else { console.error("DEBUG (JS File): Botão 'excluirDispEspecificaDoModalBtn' NÃO encontrado!");}

    } catch (e) {
        console.error("DEBUG (JS File): Erro CRÍTICO ao inicializar FullCalendar:", e);
        showAlert("Ocorreu um erro fatal ao carregar o calendário.", "danger");
    }
});