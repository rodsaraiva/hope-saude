# contas/calendar_utils.py

from datetime import time, timedelta, date, datetime
from django.utils import timezone
from django.urls import reverse # Para gerar URLs dentro dos eventos, se necessário

from .models import Agendamento, RegraDisponibilidade
# Se BloqueioTempo foi removido, não importar. Se ainda usa para algo, importe.

def gerar_eventos_completos_para_calendario_profissional(perfil_profissional, data_inicio_periodo_geral, data_fim_periodo_geral, duracao_consulta_padrao_timedelta):
    """
    Gera todos os eventos (disponibilidades, agendamentos) para o calendário
    de visualização do próprio profissional.
    """
    tz_padrao = timezone.get_default_timezone()
    all_events = []

    # Cores (podem ser movidas para settings ou constantes do app se preferir)
    cor_disponivel_bloco = '#5cb85c' 
    borda_cor_disponivel_bloco = '#4cae4c'
    # cor_bloqueio_fundo = '#e9ecef' # Removido pois BloqueioTempo foi removido

    # 1. Processar Regras de Disponibilidade (Semanal e Específica)
    todas_as_regras_disponibilidade = perfil_profissional.regras_disponibilidade.all()
    for regra in todas_as_regras_disponibilidade:
        if regra.tipo_regra == 'SEMANAL':
            if regra.dia_semana is not None and regra.hora_inicio_recorrente and regra.hora_fim_recorrente:
                fc_day = (regra.dia_semana + 1) % 7
                all_events.append({
                    'title': 'Disponível', 
                    'groupId': f'regra_disp_{regra.id}',
                    'daysOfWeek': [ fc_day ], 
                    'startTime': regra.hora_inicio_recorrente.strftime('%H:%M:%S'),
                    'endTime': regra.hora_fim_recorrente.strftime('%H:%M:%S'), 
                    'display': 'block', 
                    'color': cor_disponivel_bloco, 
                    'borderColor': borda_cor_disponivel_bloco,
                    'extendedProps': {'tipo': 'disponibilidade_semanal', 'id_original': regra.id}
                })
        elif regra.tipo_regra == 'ESPECIFICA':
            if regra.data_hora_inicio_especifica and regra.data_hora_fim_especifica:
                start_dt = regra.data_hora_inicio_especifica.astimezone(tz_padrao)
                end_dt = regra.data_hora_fim_especifica.astimezone(tz_padrao)
                if start_dt < data_fim_periodo_geral and end_dt > data_inicio_periodo_geral:
                    # Para o calendário do profissional, mostramos o bloco específico inteiro
                    all_events.append({
                        'title': 'Disponível (Específico)', 
                        'start': start_dt.isoformat(),
                        'end': end_dt.isoformat(),
                        'color': cor_disponivel_bloco, 
                        'borderColor': borda_cor_disponivel_bloco,
                        'id': f'regra_disp_esp_{regra.id}',
                        'extendedProps': {'tipo': 'regra_disponibilidade_especifica', 'id_original': regra.id}
                    })
    
    # 2. Agendamentos
    agendamentos_objs = perfil_profissional.agendamentos.filter(
        data_hora__gte=data_inicio_periodo_geral, data_hora__lt=data_fim_periodo_geral
    )
    for ag in agendamentos_objs:
        paciente_full_name = ag.paciente.user.get_full_name()
        paciente_display_name = paciente_full_name or ag.paciente.user.username
        
        cor_agendamento = '#0d6efd'; borda_cor_agendamento = '#0a58ca' # Confirmado
        if ag.status == 'PENDENTE': cor_agendamento = '#ffc107'; borda_cor_agendamento = '#cc9a06'
        elif ag.status == 'REALIZADO': cor_agendamento = '#198754'; borda_cor_agendamento = '#146c43'
        elif ag.status == 'CANCELADO': cor_agendamento = '#dc3545'; borda_cor_agendamento = '#b02a37'

        all_events.append({
            'title': f"Consulta: {paciente_display_name} ({ag.get_status_display()})",
            'start': ag.data_hora.isoformat(), 
            'end': (ag.data_hora + duracao_consulta_padrao_timedelta).isoformat(),
            'color': cor_agendamento, 
            'borderColor': borda_cor_agendamento,
            'id': f'ag_{ag.id}',
            'extendedProps': {'tipo': 'agendamento', 'id_original': ag.id, 'status': ag.status}
        })
        
    return all_events


def gerar_slots_disponiveis_para_paciente(perfil_profissional, hoje, dias_a_mostrar, duracao_consulta_timedelta):
    """
    Gera apenas os slots 'Disponível' para o calendário de agendamento do paciente,
    considerando regras, agendamentos existentes.
    """
    data_fim_periodo_calendario = hoje + timedelta(days=dias_a_mostrar)
    tz_padrao = timezone.get_default_timezone()
    agora = timezone.now()
    fim_busca_geral_agendamentos = timezone.make_aware(datetime.combine(data_fim_periodo_calendario, time.max), tz_padrao)

    regras_disponibilidade_prof = perfil_profissional.regras_disponibilidade.all()
    agendamentos_existentes = Agendamento.objects.filter(
        profissional=perfil_profissional,
        data_hora__gte=agora, 
        data_hora__lt=fim_busca_geral_agendamentos,
        status__in=['PENDENTE', 'CONFIRMADO']
    ).values_list('data_hora', flat=True)
    booked_slots_set = set(agendamentos_existentes)

    all_potential_slots_set = set()

    for i in range(dias_a_mostrar):
        dia_atual_iter = hoje + timedelta(days=i)
        dia_semana_atual_iter = dia_atual_iter.weekday()

        for regra in regras_disponibilidade_prof:
            if regra.tipo_regra == 'SEMANAL' and regra.dia_semana == dia_semana_atual_iter:
                if regra.hora_inicio_recorrente and regra.hora_fim_recorrente:
                    hora_corrente = regra.hora_inicio_recorrente
                    while hora_corrente < regra.hora_fim_recorrente:
                        slot_dt = timezone.make_aware(datetime.combine(dia_atual_iter, hora_corrente), tz_padrao)
                        if (datetime.combine(date.min, hora_corrente) + duracao_consulta_timedelta).time() <= regra.hora_fim_recorrente:
                             all_potential_slots_set.add(slot_dt)
                        hora_corrente = (datetime.combine(date.min, hora_corrente) + duracao_consulta_timedelta).time()
            
            elif regra.tipo_regra == 'ESPECIFICA':
                if regra.data_hora_inicio_especifica and regra.data_hora_fim_especifica:
                    start_dt_especifica = regra.data_hora_inicio_especifica.astimezone(tz_padrao)
                    end_dt_especifica = regra.data_hora_fim_especifica.astimezone(tz_padrao)
                    if start_dt_especifica < timezone.make_aware(datetime.combine(data_fim_periodo_calendario, time.min), tz_padrao) and end_dt_especifica > agora:
                        current_slot_especifico = start_dt_especifica
                        if current_slot_especifico.date() < dia_atual_iter and dia_atual_iter <= end_dt_especifica.date(): # Regra começa antes do dia_atual_iter
                            current_slot_especifico = timezone.make_aware(datetime.combine(dia_atual_iter, time.min), tz_padrao)
                        
                        while current_slot_especifico < end_dt_especifica and current_slot_especifico.date() == dia_atual_iter:
                            if current_slot_especifico + duracao_consulta_timedelta <= end_dt_especifica:
                                all_potential_slots_set.add(current_slot_especifico)
                            current_slot_especifico += duracao_consulta_timedelta
    
    slots_validos_final = []
    for slot in sorted(list(all_potential_slots_set)):
        if slot > agora and slot not in booked_slots_set:
            slots_validos_final.append(slot)

    slots_disponiveis_agrupados = {}
    for slot in slots_validos_final:
        dia = slot.date()
        if dia not in slots_disponiveis_agrupados: slots_disponiveis_agrupados[dia] = []
        slots_disponiveis_agrupados[dia].append(slot)

    calendar_events = []
    for data_loop, slots_loop in slots_disponiveis_agrupados.items():
        for slot_inicio in slots_loop:
            slot_fim_evento = slot_inicio + duracao_consulta_timedelta
            evento = {
                'title': 'Disponível',
                'start': slot_inicio.isoformat(),
                'end': slot_fim_evento.isoformat(),
                'extendedProps': {
                    'booking_url': reverse('contas:criar_agendamento', args=[perfil_profissional.id, slot_inicio.isoformat()])
                 }
            }
            calendar_events.append(evento)
    return calendar_events