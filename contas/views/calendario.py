from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..calendar_utils import gerar_eventos_completos_para_calendario_profissional


@login_required
def calendario_profissional(request):
    """View para o calendário do profissional"""
    if not hasattr(request.user, 'perfil_profissional'):
        messages.error(request, "Apenas profissionais podem acessar esta página.")
        return redirect('contas:index')

    perfil = request.user.perfil_profissional
    
    # Toda a lógica de geração de eventos foi movida para calendar_utils.
    # A view apenas chama a função.
    calendar_events = gerar_eventos_completos_para_calendario_profissional(
        perfil_profissional=perfil
    )
    
    contexto = {
        'calendar_events_data': calendar_events,
    }
    return render(request, 'contas/calendario_profissional.html', contexto) 