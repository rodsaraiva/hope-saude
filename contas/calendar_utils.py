# contas/calendar_utils.py

from datetime import time, timedelta, date, datetime
from django.utils import timezone
from django.urls import reverse # Para gerar URLs dentro dos eventos, se necessário

from .models import Agendamento, RegraDisponibilidade
# Se BloqueioTempo foi removido, não importar. Se ainda usa para algo, importe.

def gerar_eventos_completos_para_calendario_profissional(perfil_profissional, duracao_consulta_padrao=timedelta(hours=1)):
    """
    Gera todos os eventos (disponibilidades, agendamentos) para o calendário
    de visualização do próprio profissional.
    Esta versão inclui a lógica de agrupar blocos de disponibilidade específica contíguos.
    """
    tz_padrao = timezone.get_default_timezone()
    agora = timezone.now()
    
    # Período de visualização padrão
    data_inicio_periodo_geral = agora - timedelta(days=30)
    data_fim_periodo_geral = agora + timedelta(days=90)

    # Busca de dados do banco
    regras_qs = perfil_profissional.regras_disponibilidade.all().order_by('data_hora_inicio_especifica', 'hora_inicio_recorrente')
    agendamentos_qs = perfil_profissional.agendamentos.filter(
        data_hora__gte=data_inicio_periodo_geral, data_hora__lt=data_fim_periodo_geral
    )

    all_events = []
    cor_disponivel_bloco = '#5cb85c'
    borda_cor_disponivel_bloco = '#4cae4c'
    texto_cor_disponivel = '#FFFFFF'

    # 1. Processar Regras de Disponibilidade Semanal
    for regra in regras_qs.filter(tipo_regra='SEMANAL'):
        if regra.dia_semana is not None and regra.hora_inicio_recorrente and regra.hora_fim_recorrente:
            fc_day = (regra.dia_semana + 1) % 7
            all_events.append({
                'title': 'Disponível',
                'groupId': f'regra_disp_semanal_{regra.id}',
                'daysOfWeek': [fc_day],
                'startTime': regra.hora_inicio_recorrente.strftime('%H:%M:%S'),
                'endTime': regra.hora_fim_recorrente.strftime('%H:%M:%S'),
                'display': 'block',
                'color': cor_disponivel_bloco,
                'borderColor': borda_cor_disponivel_bloco,
                'textColor': texto_cor_disponivel,
                'extendedProps': {'tipo': 'disponibilidade_semanal', 'id_original': regra.id}
            })

    # 2. Processar e AGRUPAR Regras de Disponibilidade Específicas Contíguas
    regras_especificas = regras_qs.filter(tipo_regra='ESPECIFICA').order_by('data_hora_inicio_especifica')
    
    merged_specific_slots = []
    current_merged_event = None

    for regra in regras_especificas:
        if regra.data_hora_inicio_especifica and regra.data_hora_fim_especifica:
            start_dt = regra.data_hora_inicio_especifica.astimezone(tz_padrao)
            end_dt = regra.data_hora_fim_especifica.astimezone(tz_padrao)

            if not (start_dt < data_fim_periodo_geral and end_dt > data_inicio_periodo_geral):
                continue

            if current_merged_event is None:
                current_merged_event = {'start': start_dt, 'end': end_dt, 'ids_originais': [regra.id]}
            elif start_dt == current_merged_event['end']:
                current_merged_event['end'] = end_dt
                current_merged_event['ids_originais'].append(regra.id)
            else:
                merged_specific_slots.append(current_merged_event)
                current_merged_event = {'start': start_dt, 'end': end_dt, 'ids_originais': [regra.id]}
    
    if current_merged_event:
        merged_specific_slots.append(current_merged_event)

    for slot_agrupado in merged_specific_slots:
        all_events.append({
            'title': 'Disponível',
            'start': slot_agrupado['start'].isoformat(),
            'end': slot_agrupado['end'].isoformat(),
            'color': cor_disponivel_bloco,
            'borderColor': borda_cor_disponivel_bloco,
            'textColor': texto_cor_disponivel,
            'id': f'regra_disp_esp_agrupada_{"_".join(map(str, slot_agrupado["ids_originais"]))}',
            'extendedProps': {'tipo': 'disponibilidade_especifica_agrupada', 'ids_originais': slot_agrupado['ids_originais']}
        })

    # 3. Adicionar Agendamentos
    for ag in agendamentos_qs:
        paciente_display_name = ag.paciente.user.get_full_name() or ag.paciente.user.username
        cor_agendamento, borda_cor_agendamento, texto_cor_agendamento = '#0d6efd', '#0a58ca', 'white'
        if ag.status == 'PENDENTE': cor_agendamento, borda_cor_agendamento, texto_cor_agendamento = '#ffc107', '#cc9a06', '#212529'
        elif ag.status == 'REALIZADO': cor_agendamento, borda_cor_agendamento, texto_cor_agendamento = '#198754', '#146c43', 'white'
        elif ag.status == 'CANCELADO': cor_agendamento, borda_cor_agendamento, texto_cor_agendamento = '#dc3545', '#b02a37', 'white'

        all_events.append({
            'title': f"Consulta: {paciente_display_name} ({ag.get_status_display()})",
            'start': ag.data_hora.isoformat(),
            'end': (ag.data_hora + duracao_consulta_padrao).isoformat(),
            'color': cor_agendamento,
            'borderColor': borda_cor_agendamento,
            'textColor': texto_cor_agendamento,
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
    agendamentos_existentes = Agendamento.objects.filter(  # type: ignore[attr-defined]
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


def gerar_blocos_disponiveis_para_paciente(perfil_profissional, dias_a_mostrar=7, duracao_consulta_timedelta=timedelta(hours=1), incremento_geracao_slot_timedelta=timedelta(minutes=30)):
    """
    Gera blocos de horários visuais para o calendário do paciente.
    Cada regra de disponibilidade cadastrada (específica ou semanal) vira um bloco único,
    exceto se houver agendamento ocupando parte do tempo.
    """
    hoje = timezone.localdate()
    data_fim_periodo_calendario = hoje + timedelta(days=dias_a_mostrar)
    tz_padrao = timezone.get_default_timezone()
    agora = timezone.now()
    fim_busca_geral_agendamentos = timezone.make_aware(datetime.combine(data_fim_periodo_calendario, time.max), tz_padrao)

    regras_disponibilidade_prof = perfil_profissional.regras_disponibilidade.all()
    agendamentos_existentes_objs = Agendamento.objects.filter(  # type: ignore[attr-defined]
        profissional=perfil_profissional,
        data_hora__gte=agora,
        data_hora__lt=fim_busca_geral_agendamentos,
        status__in=['PENDENTE', 'CONFIRMADO']
    )

    # Lista de intervalos ocupados
    booked_intervals = [(ag.data_hora, ag.data_hora + duracao_consulta_timedelta) for ag in agendamentos_existentes_objs]

    blocos_visuais = []
    cor_bloco = '#28a745'
    borda_bloco = '#23923d'

    for regra in regras_disponibilidade_prof:
        if regra.tipo_regra == 'SEMANAL' and regra.dia_semana is not None and regra.hora_inicio_recorrente and regra.hora_fim_recorrente:
            for i in range(dias_a_mostrar):
                dia = hoje + timedelta(days=i)
                if dia.weekday() == regra.dia_semana:
                    bloco_inicio = timezone.make_aware(datetime.combine(dia, regra.hora_inicio_recorrente), tz_padrao)
                    bloco_fim = timezone.make_aware(datetime.combine(dia, regra.hora_fim_recorrente), tz_padrao)
                    if bloco_fim <= agora:
                        continue
                    # Verifica se há agendamento ocupando parte do bloco
                    blocos_livres = [(bloco_inicio, bloco_fim)]
                    for booked_start, booked_end in booked_intervals:
                        novos_blocos = []
                        for livre_inicio, livre_fim in blocos_livres:
                            # Se não há interseção, mantém
                            if booked_end <= livre_inicio or booked_start >= livre_fim:
                                novos_blocos.append((livre_inicio, livre_fim))
                            else:
                                # Divide o bloco livre em até dois
                                if livre_inicio < booked_start:
                                    novos_blocos.append((livre_inicio, booked_start))
                                if booked_end < livre_fim:
                                    novos_blocos.append((booked_end, livre_fim))
                        blocos_livres = novos_blocos
                    for livre_inicio, livre_fim in blocos_livres:
                        if livre_fim > livre_inicio:
                            blocos_visuais.append({
                                'title': 'Horários Disponíveis',
                                'start': livre_inicio.isoformat(),
                                'end': livre_fim.isoformat(),
                                'color': cor_bloco,
                                'borderColor': borda_bloco,
                                'extendedProps': {'tipo': 'bloco_disponivel_paciente', 'id_regra': regra.id}
                            })
        elif regra.tipo_regra == 'ESPECIFICA' and regra.data_hora_inicio_especifica and regra.data_hora_fim_especifica:
            bloco_inicio = regra.data_hora_inicio_especifica.astimezone(tz_padrao)
            bloco_fim = regra.data_hora_fim_especifica.astimezone(tz_padrao)
            if bloco_fim <= agora:
                continue
            blocos_livres = [(bloco_inicio, bloco_fim)]
            for booked_start, booked_end in booked_intervals:
                novos_blocos = []
                for livre_inicio, livre_fim in blocos_livres:
                    if booked_end <= livre_inicio or booked_start >= livre_fim:
                        novos_blocos.append((livre_inicio, livre_fim))
                    else:
                        if livre_inicio < booked_start:
                            novos_blocos.append((livre_inicio, booked_start))
                        if booked_end < livre_fim:
                            novos_blocos.append((booked_end, livre_fim))
                blocos_livres = novos_blocos
            for livre_inicio, livre_fim in blocos_livres:
                if livre_fim > livre_inicio:
                    blocos_visuais.append({
                        'title': 'Horários Disponíveis',
                        'start': livre_inicio.isoformat(),
                        'end': livre_fim.isoformat(),
                        'color': cor_bloco,
                        'borderColor': borda_bloco,
                        'extendedProps': {'tipo': 'bloco_disponivel_paciente', 'id_regra': regra.id}
                    })
    return blocos_visuais