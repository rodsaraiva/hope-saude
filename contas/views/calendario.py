from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
import json

from ..calendar_utils import gerar_eventos_completos_para_calendario_profissional


@login_required
def calendario_profissional(request):
    """View para o calendário do profissional"""
    if not hasattr(request.user, 'perfil_profissional'):
        messages.error(request, "Apenas profissionais podem acessar esta página.")
        return redirect('contas:index')

    perfil = request.user.perfil_profissional
    
    # Buscar agendamentos do profissional
    agendamentos = perfil.agendamentos.all().order_by('data_hora')
    
    # Converter agendamentos para formato JSON
    agendamentos_data = []
    for agendamento in agendamentos:
        agendamentos_data.append({
            'id': agendamento.id,
            'data_hora': agendamento.data_hora.isoformat(),
            'paciente_nome': agendamento.paciente.user.get_full_name() or agendamento.paciente.user.username,
            'status': agendamento.status.lower(),
            'url_videochamada': agendamento.url_videochamada
        })
    
    # Toda a lógica de geração de eventos foi movida para calendar_utils.
    # A view apenas chama a função.
    calendar_events = gerar_eventos_completos_para_calendario_profissional(
        perfil_profissional=perfil
    )
    
    contexto = {
        'calendar_events_data': calendar_events,
        'agendamentos_json': json.dumps(agendamentos_data, cls=DjangoJSONEncoder),
    }
    return render(request, 'contas/calendario_profissional.html', contexto) 