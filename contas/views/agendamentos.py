from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from datetime import timedelta, datetime
import stripe

from ..models import PerfilProfissional, Agendamento, RegraDisponibilidade
from .utils import validate_agendamento_permission


@login_required
def meus_agendamentos(request):
    """View para listar os agendamentos do usuário logado"""
    user = request.user
    agendamentos_futuros = None
    agendamentos_ativos = None
    agendamentos_passados = None
    is_profissional = False

    now = timezone.now()
    janela_ativa = timedelta(hours=1, minutes=30)

    try:
        agendamentos_qs = None
        if hasattr(user, 'perfil_paciente'):
            perfil = user.perfil_paciente
            agendamentos_qs = Agendamento.objects.filter(paciente=perfil)  # type: ignore
        elif hasattr(user, 'perfil_profissional'):
            perfil = user.perfil_profissional
            is_profissional = True
            agendamentos_qs = Agendamento.objects.filter(profissional=perfil)  # type: ignore
        
        if agendamentos_qs:
            # Consultas que ainda não começaram
            agendamentos_futuros = agendamentos_qs.filter(data_hora__gt=now).order_by('data_hora')
            
            # Consultas que começaram recentemente (dentro da "janela ativa")
            agendamentos_ativos = agendamentos_qs.filter(
                data_hora__lte=now,
                data_hora__gt=now - janela_ativa
            ).order_by('data_hora')

            # Consultas que começaram há mais tempo que a "janela ativa"
            agendamentos_passados = agendamentos_qs.filter(
                data_hora__lte=now - janela_ativa
            ).order_by('-data_hora')

    except Exception as e:
         messages.error(request, f"Ocorreu um erro ao buscar seus agendamentos: {e}")

    contexto = {
        'agendamentos_futuros': agendamentos_futuros,
        'agendamentos_ativos': agendamentos_ativos,
        'agendamentos_passados': agendamentos_passados,
        'is_profissional': is_profissional,
    }
    return render(request, 'contas/meus_agendamentos.html', contexto)


@login_required
@require_POST
def cancelar_agendamento(request, agendamento_id):
    """View para cancelar um agendamento"""
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    user = request.user

    # Verifica se o usuário tem permissão para cancelar este agendamento
    if not validate_agendamento_permission(user, agendamento):
        messages.error(request, "Você não tem permissão para cancelar este agendamento.")
        return redirect('contas:meus_agendamentos')

    # Verifica se o agendamento PODE ser cancelado
    if agendamento.status not in ['PENDENTE', 'CONFIRMADO']:
        messages.warning(request, f"Este agendamento não pode mais ser cancelado (Status: {agendamento.get_status_display()}).")
        return redirect('contas:meus_agendamentos')

    # Prepara informações para o email ANTES de mudar o status
    paciente_email = agendamento.paciente.user.email
    profissional_email = agendamento.profissional.user.email

    paciente_full_name = agendamento.paciente.user.get_full_name()
    paciente_nome = paciente_full_name or agendamento.paciente.user.username

    profissional_full_name = agendamento.profissional.user.get_full_name()
    profissional_nome = profissional_full_name or agendamento.profissional.user.username

    data_hora_agendamento = agendamento.data_hora

    # Quem está cancelando?
    perfil_paciente_associado = hasattr(user, 'perfil_paciente') and agendamento.paciente == user.perfil_paciente
    cancelado_por = "Paciente" if perfil_paciente_associado else "Profissional"
    email_destinatario = profissional_email if perfil_paciente_associado else paciente_email
    nome_destinatario = profissional_nome if perfil_paciente_associado else paciente_nome

    template_txt = 'contas/email/agendamento_cancelado_outro.txt'
    assunto = f"Agendamento Cancelado: {paciente_nome} com {profissional_nome}"

    # Tenta cancelar e enviar email
    try:
        agendamento.status = 'CANCELADO'
        agendamento.save()
        messages.success(request, "Agendamento cancelado com sucesso.")

        # Tenta enviar email para a outra parte
        try:
            contexto_email = {
                'destinatario_nome': nome_destinatario,
                'paciente_nome': paciente_nome,
                'profissional_nome': profissional_nome,
                'data_hora_agendamento': data_hora_agendamento,
                'cancelado_por': cancelado_por,
            }
            corpo_email_txt = render_to_string(template_txt, contexto_email)

            if email_destinatario:
                send_mail(
                    assunto,
                    corpo_email_txt,
                    settings.DEFAULT_FROM_EMAIL,
                    [email_destinatario],
                    fail_silently=False,
                )
            else:
                 messages.warning(request, "Agendamento cancelado, mas não foi possível notificar a outra parte (email não encontrado).")

        except Exception as e_mail:
            print(f"Erro ao enviar email de cancelamento: {e_mail}")
            messages.warning(request, f"Agendamento cancelado, mas houve um erro ao enviar o email de notificação.")

    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao cancelar o agendamento: {e}")

    return redirect('contas:meus_agendamentos')


@login_required
@require_POST
def criar_agendamento(request, profissional_id, timestamp_str):
    """View para criar um agendamento"""
    # Configura a chave da API do Stripe para esta requisição
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    user = request.user
    if not hasattr(user, 'perfil_paciente'):
        messages.error(request, "Apenas pacientes podem agendar consultas.")
        return redirect('contas:lista_profissionais')

    perfil_paciente = user.perfil_paciente
    profissional = get_object_or_404(PerfilProfissional, pk=profissional_id)

    # Verifica se o profissional definiu um valor para a consulta
    if not profissional.valor_consulta or profissional.valor_consulta <= 0:
        messages.error(request, "Este profissional não está aceitando agendamentos pagos no momento.")
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)

    try:
        slot_datetime = datetime.fromisoformat(timestamp_str).astimezone(timezone.get_default_timezone())
    except ValueError:
        messages.error(request, "Horário inválido selecionado.")
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)

    # Revalidação de horário vago e no futuro
    if Agendamento.objects.filter(profissional=profissional, data_hora=slot_datetime, status__in=['PENDENTE', 'CONFIRMADO']).exists():  # type: ignore
        messages.error(request, "Desculpe, este horário foi agendado por outra pessoa. Por favor, escolha outro.")
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)
    if slot_datetime <= timezone.now():
        messages.error(request, "Não é possível agendar horários no passado.")
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)

    # Cria o Agendamento com status de pagamento pendente
    novo_agendamento = Agendamento.objects.create(  # type: ignore
        paciente=perfil_paciente,
        profissional=profissional,
        data_hora=slot_datetime,
        status='PENDENTE',
        status_pagamento='PENDENTE'
    )
    
    # --- NOVA LÓGICA: dividir/excluir disponibilidade ---
    slot_fim = slot_datetime + timedelta(hours=1)  # ou use a duração correta
    # Busca todas as regras de disponibilidade específicas que abrangem o slot
    regras = RegraDisponibilidade.objects.filter(  # type: ignore[attr-defined]
        profissional=profissional,
        tipo_regra='ESPECIFICA',
        data_hora_inicio_especifica__lt=slot_fim,
        data_hora_fim_especifica__gt=slot_datetime
    )
    for regra in regras:
        inicio = regra.data_hora_inicio_especifica
        fim = regra.data_hora_fim_especifica
        # Caso 1: o slot ocupa toda a disponibilidade
        if inicio >= slot_datetime and fim <= slot_fim:
            regra.delete()
        # Caso 2: o slot está no meio da disponibilidade (divide em duas)
        elif inicio < slot_datetime and fim > slot_fim:
            regra.data_hora_fim_especifica = slot_datetime
            regra.save()
            RegraDisponibilidade.objects.create(  # type: ignore[attr-defined]
                profissional=profissional,
                tipo_regra='ESPECIFICA',
                data_hora_inicio_especifica=slot_fim,
                data_hora_fim_especifica=fim
            )
        # Caso 3: o slot está no início da disponibilidade
        elif inicio < slot_datetime < fim <= slot_fim:
            regra.data_hora_fim_especifica = slot_datetime
            regra.save()
        # Caso 4: o slot está no final da disponibilidade
        elif slot_datetime <= inicio < slot_fim < fim:
            regra.data_hora_inicio_especifica = slot_fim
            regra.save()
    # --- FIM DA LÓGICA ---

    try:
        # Cria um PaymentIntent no Stripe
        valor_em_centavos = int(profissional.valor_consulta * 100)
        
        intent = stripe.PaymentIntent.create(
            amount=valor_em_centavos,
            currency='brl',
            metadata={'agendamento_id': novo_agendamento.id}
        )
        
        # Salva o ID do PaymentIntent no nosso modelo de Agendamento
        novo_agendamento.pagamento_id = intent.id
        novo_agendamento.save()
        
        # Redireciona para a nova página de pagamento
        return redirect('contas:processar_pagamento', agendamento_id=novo_agendamento.id)

    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao iniciar o pagamento: {e}")
        # Se falhar ao comunicar com o Stripe, podemos deletar o agendamento recém-criado
        novo_agendamento.delete()
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)


@login_required
@require_POST
def confirmar_agendamento(request, agendamento_id):
    """View para o profissional confirmar um agendamento pendente"""
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        messages.error(request, "Apenas profissionais podem confirmar agendamentos.")
        return redirect('contas:meus_agendamentos')

    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    perfil_profissional = user.perfil_profissional

    # Verifica se o profissional logado é o profissional deste agendamento
    if agendamento.profissional != perfil_profissional:
        messages.error(request, "Você não tem permissão para confirmar este agendamento.")
        return redirect('contas:meus_agendamentos')

    # Verifica se o agendamento está realmente pendente
    if agendamento.status != 'PENDENTE':
        messages.warning(request, f"Este agendamento não pode ser confirmado (Status: {agendamento.get_status_display()}).")
        return redirect('contas:meus_agendamentos')

    # Se tudo OK, confirma o agendamento
    try:
        agendamento.status = 'CONFIRMADO'
        agendamento.save()
        messages.success(request, f"Agendamento com {agendamento.paciente.user.username} confirmado com sucesso!")

        # ENVIAR EMAIL PARA O PACIENTE
        try:
            assunto_paciente = f"Seu Agendamento Confirmado: {agendamento.profissional.user.get_full_name()}"
            contexto_email_paciente = {
                'paciente_nome': agendamento.paciente.user.get_full_name() or agendamento.paciente.user.username,
                'profissional_nome': agendamento.profissional.user.get_full_name() or agendamento.profissional.user.username,
                'data_hora_agendamento': agendamento.data_hora,
                'link_meus_agendamentos': request.build_absolute_uri(reverse('contas:meus_agendamentos')),
            }
            corpo_email_paciente_txt = render_to_string('contas/email/agendamento_confirmado_paciente.txt', contexto_email_paciente)

            send_mail(
                assunto_paciente,
                corpo_email_paciente_txt,
                settings.DEFAULT_FROM_EMAIL,
                [agendamento.paciente.user.email],
                fail_silently=False,
            )
        except Exception as e_mail:
            messages.warning(request, f"Agendamento confirmado, mas houve um erro ao notificar o paciente por email: {e_mail}")

    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao confirmar o agendamento: {e}")

    return redirect('contas:meus_agendamentos')


@login_required
@require_POST
def marcar_realizado(request, agendamento_id):
    """View para o profissional marcar um agendamento como realizado"""
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        messages.error(request, "Apenas profissionais podem marcar agendamentos como realizados.")
        return redirect('contas:meus_agendamentos')

    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    perfil_profissional = user.perfil_profissional

    # Verifica se o profissional logado é o profissional deste agendamento
    if agendamento.profissional != perfil_profissional:
        messages.error(request, "Você não tem permissão para alterar este agendamento.")
        return redirect('contas:meus_agendamentos')

    # Verifica se o agendamento está CONFIRMADO e se já passou
    if agendamento.status != 'CONFIRMADO':
        messages.warning(request, "Apenas agendamentos confirmados podem ser marcados como realizados.")
        return redirect('contas:meus_agendamentos')

    if agendamento.data_hora > timezone.now():
         messages.warning(request, "Ainda não é possível marcar este agendamento futuro como realizado.")
         return redirect('contas:meus_agendamentos')

    # Se tudo OK, marca como realizado
    try:
        agendamento.status = 'REALIZADO'
        agendamento.save()
        messages.success(request, f"Agendamento com {agendamento.paciente.user.username} marcado como realizado.")
    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao marcar o agendamento como realizado: {e}")

    return redirect('contas:meus_agendamentos')


@login_required
def sala_videochamada(request, agendamento_id):
    """Renderiza a página que irá hospedar a videochamada embutida"""
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    user = request.user

    # Validação de permissão
    if not validate_agendamento_permission(user, agendamento):
        messages.error(request, "Você não tem permissão para acessar esta sala.")
        return redirect('contas:meus_agendamentos')

    # Validação de status
    if agendamento.status != 'CONFIRMADO':
        messages.error(request, "Esta consulta não está confirmada e a sala de vídeo não pode ser acessada.")
        return redirect('contas:meus_agendamentos')

    contexto = {
        'agendamento': agendamento,
    }
    return render(request, 'contas/sala_videochamada.html', contexto) 