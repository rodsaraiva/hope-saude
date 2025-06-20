# contas/views.py

from datetime import time, timedelta, date, datetime # Importa timedelta e date
import requests # Para fazer chamadas HTTP à API do Daily.co
import stripe
import json # Importa json
from django.core.exceptions import ValidationError
from django.shortcuts import render, get_object_or_404, redirect # Importe get_object_or_404
from django.contrib.auth.decorators import login_required # Importa o decorator de login obrigatório
from django.views.decorators.http import require_POST # Importa decorator para exigir POST
from django.db.models import Q # Importa Q objects para buscas complexas
from django.utils import timezone # Importa timezone
from django.contrib import messages
from django.core.paginator import Paginator # Importa o Paginator
from django.db import IntegrityError # Importa IntegrityError
from django.core.mail import send_mail # Para enviar emails
from django.template.loader import render_to_string # Para renderizar templates de email
from django.conf import settings # Para pegar DEFAULT_FROM_EMAILsudo apt upgrade python3
from django.urls import reverse
from django.http import JsonResponse # Importa JsonResponse
from django.views.generic import ListView
from django.views.generic.edit import UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from dateutil import parser

from .calendar_utils import gerar_eventos_completos_para_calendario_profissional, gerar_blocos_disponiveis_para_paciente

from .models import (
    PerfilProfissional, PerfilPaciente, Especialidade, Agendamento,
    RegraDisponibilidade, Avaliacao
    # Certifique-se que Disponibilidade e DisponibilidadeAvulsa foram removidos desta lista
)

from .forms import (
    RegistroUsuarioForm, PerfilProfissionalForm, PerfilPacienteForm,
    CustomAuthenticationForm, RegraDisponibilidadeForm
    # Assegure-se de que DisponibilidadeForm e DisponibilidadeAvulsaForm foram removidos
    # Poderíamos adicionar RegraDisponibilidadeForm aqui depois, quando ele for criado.
)

def api_success_response(data=None, status_code=200):
    """
    Gera uma resposta JSON padronizada para sucesso.
    """
    response = {'status': 'success'}
    if data is not None:
        response['data'] = data
    return JsonResponse(response, status=status_code)

def api_error_response(message, error_code=None, status_code=400):
    """
    Gera uma resposta JSON padronizada para erro.
    """
    response = {'status': 'error', 'message': message}
    if error_code is not None:
        response['error_code'] = error_code
    return JsonResponse(response, status=status_code)

# CLASSES CBV


class EditarPerfilView(LoginRequiredMixin, UpdateView):
    template_name = 'contas/editar_perfil.html'
    success_url = reverse_lazy('contas:meu_perfil')

    def get_object(self, queryset=None):
        """
        Retorna o objeto de perfil (Profissional ou Paciente)
        que o usuário está autorizado a editar.
        """
        if hasattr(self.request.user, 'perfil_profissional'):
            return self.request.user.perfil_profissional
        elif hasattr(self.request.user, 'perfil_paciente'):
            return self.request.user.perfil_paciente
        # Se não tiver nenhum perfil, idealmente não deveria chegar aqui
        # se o fluxo de registro estiver correto, mas podemos tratar por segurança.
        return None

    def get_form_class(self):
        """
        Retorna a classe do formulário apropriada baseada no tipo de perfil.
        """
        if hasattr(self.request.user, 'perfil_profissional'):
            return PerfilProfissionalForm
        elif hasattr(self.request.user, 'perfil_paciente'):
            return PerfilPacienteForm
        return None # Deveria levantar um erro se não encontrar um form

    def get(self, request, *args, **kwargs):
        # Sobrescrevemos o get para tratar o caso de usuário sem perfil
        self.object = self.get_object()
        if self.object is None:
            messages.error(self.request, "Não foi possível encontrar um perfil para editar.")
            return redirect('contas:meu_perfil')
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        # Adiciona a mensagem de sucesso antes de redirecionar
        messages.success(self.request, "Perfil atualizado com sucesso!")
        return super().form_valid(form)

    def form_invalid(self, form):
        # Adiciona uma mensagem de erro genérica
        messages.error(self.request, "Erro ao atualizar o perfil. Verifique os campos.")
        return super().form_invalid(form)





# View para a página inicial
def index(request):
    # Por enquanto, apenas renderiza um template HTML simples
    return render(request, 'contas/index.html')

# View para a lista de profissionais
def lista_profissionais(request):
    query = request.GET.get('q')
    selected_specialty_ids = request.GET.getlist('especialidade')

    # Começa com todos os perfis (ou um queryset vazio se preferir iniciar filtrando)
    profissionais_queryset = PerfilProfissional.objects.all().order_by('user__first_name') # Adiciona uma ordem padrão

    # Aplica filtro de especialidades selecionadas (se houver)
    valid_specialty_ids = []
    if selected_specialty_ids:
        try:
            valid_specialty_ids = [int(id) for id in selected_specialty_ids]
            if valid_specialty_ids:
                profissionais_queryset = profissionais_queryset.filter(especialidades__id__in=valid_specialty_ids)
        except ValueError:
            messages.warning(request, "Seleção de especialidade inválida ignorada.")
            valid_specialty_ids = [] # Reseta se inválido

    # Aplica filtro de busca textual (se houver)
    if query:
        profissionais_queryset = profissionais_queryset.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query) |
            Q(especialidades__nome__icontains=query) |
            Q(bio__icontains=query)
        )

    # Remove duplicatas APÓS todos os filtros
    profissionais_queryset = profissionais_queryset.distinct()

    # --- Paginação ---
    # Cria o objeto Paginator (10 itens por página, por exemplo)
    paginator = Paginator(profissionais_queryset, 10)
    # Pega o número da página da URL (?page=...)
    page_number = request.GET.get('page')
    # Obtém o objeto Page para a página solicitada (lida com erros de página inválida)
    page_obj = paginator.get_page(page_number)
    # --- Fim da Paginação ---

    todas_especialidades = Especialidade.objects.all()

    contexto = {
        # Passa o objeto Page para o template, em vez da lista completa
        'page_obj': page_obj,
        'todas_especialidades': todas_especialidades,
        'search_query': query,
        # Passa os IDs como inteiros para o template (se válidos)
        'selected_specialty_ids': valid_specialty_ids,
    }
    return render(request, 'contas/lista_profissionais.html', contexto)

# View para a página de registro
def registro(request):
    if request.method == 'POST': # Se o formulário foi enviado (requisição POST)
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid(): # Se o formulário passou nas validações
            user = form.save() # Salva o objeto User (UserCreationForm cuida disso)
            tipo_conta = form.cleaned_data.get('tipo_conta') # Pega o valor selecionado

            # Cria o perfil apropriado ligado ao usuário recém-criado
            if tipo_conta == 'PACIENTE':
                PerfilPaciente.objects.create(user=user)
            elif tipo_conta == 'PROFISSIONAL':
                # Cria o perfil profissional (campos obrigatórios agora são opcionais no BD)
                PerfilProfissional.objects.create(user=user)

            messages.success(request, f'Conta criada com sucesso para {user.username}! Você já pode fazer login.') # Mensagem de sucesso (opcional)
            return redirect('login') # Redireciona para a página de login
        else:
            # Se o formulário for inválido, mensagens de erro serão exibidas no template
            messages.error(request, 'Por favor, corrija os erros abaixo.') # Mensagem de erro (opcional)

    else: # Se for uma requisição GET (primeira vez acessando a página)
        form = RegistroUsuarioForm() # Cria um formulário vazio

    # Renderiza o template passando o formulário (vazio ou com erros)
    return render(request, 'contas/registro.html', {'form': form})


def perfil_profissional_detail(request, pk):
    perfil = get_object_or_404(PerfilProfissional, pk=pk)
    
    # Parâmetros para a geração de horários
    duracao_consulta = timedelta(hours=1)
    
    # A complexidade foi movida para calendar_utils. A view apenas chama a função.
    calendar_events = gerar_blocos_disponiveis_para_paciente(
        perfil_profissional=perfil,
        duracao_consulta_timedelta=duracao_consulta
    )
    
    contexto = {
        'perfil': perfil,
        'calendar_events_data': calendar_events,
        'duracao_consulta_minutos': int(duracao_consulta.total_seconds() // 60),
    }
    return render(request, 'contas/perfil_profissional_detail.html', contexto)


# View para a página "Meu Perfil" do usuário logado
@login_required # Garante que apenas usuários logados acessem esta view
def meu_perfil(request):
    user = request.user # Pega o objeto User do usuário logado
    contexto = {'user': user} # Começa o contexto com o usuário

    # Tenta encontrar um perfil associado e adiciona ao contexto
    try:
        perfil_paciente = user.perfil_paciente # Usando o related_name que definimos
        contexto['perfil_paciente'] = perfil_paciente
    except PerfilPaciente.DoesNotExist:
        pass # Se não for paciente, não faz nada aqui

    try:
        perfil_profissional = user.perfil_profissional # Usando related_name
        contexto['perfil_profissional'] = perfil_profissional
    except PerfilProfissional.DoesNotExist:
        pass # Se não for profissional, não faz nada aqui

    # Verifica se algum perfil foi encontrado (deve acontecer se o registro funcionou)
    if 'perfil_paciente' not in contexto and 'perfil_profissional' not in contexto:
        # Situação inesperada: usuário logado sem perfil.
        # Poderíamos redirecionar para completar o perfil ou mostrar uma mensagem.
        # Por enquanto, vamos adicionar uma mensagem de erro simples no contexto.
        contexto['erro_perfil'] = "Não foi possível encontrar um perfil associado à sua conta."

    # Renderiza um template único para "meu perfil"
    return render(request, 'contas/meu_perfil.html', contexto)


# View para editar o perfil
# @login_required
# def editar_perfil(request):
#     user = request.user
#     perfil = None
#     form_class = None # Variável para guardar a classe do formulário correto

#     # Verifica qual perfil o usuário tem e define o form apropriado
#     if hasattr(user, 'perfil_profissional'):
#         perfil = user.perfil_profissional
#         form_class = PerfilProfissionalForm
#     elif hasattr(user, 'perfil_paciente'):
#         perfil = user.perfil_paciente
#         form_class = PerfilPacienteForm
#     else:
#         # Caso inesperado: usuário sem perfil associado
#         messages.error(request, "Não foi possível encontrar um perfil para editar.")
#         return redirect('contas:meu_perfil')

#     if request.method == 'POST':
#         # Cria a instância do formulário correto (form_class) com os dados POST e a instância do perfil
#         form = form_class(request.POST, instance=perfil)
#         if form.is_valid():
#             form.save()
#             messages.success(request, "Perfil atualizado com sucesso!")
#             return redirect('contas:meu_perfil')
#         else:
#             messages.error(request, "Erro ao atualizar o perfil. Verifique os campos.")
#     else: # GET request
#         # Cria a instância do formulário correto (form_class) pré-preenchida com a instância do perfil
#         form = form_class(instance=perfil)

#     contexto = {
#         'form': form
#     }
#     # Renderiza o MESMO template de edição
#     return render(request, 'contas/editar_perfil.html', contexto)



# View para listar os agendamentos do usuário logado
@login_required
def meus_agendamentos(request):
    user = request.user
    agendamentos_futuros = None
    agendamentos_ativos = None  # Nova lista
    agendamentos_passados = None
    is_profissional = False # Flag para ajudar o template

    now = timezone.now() # Pega a data e hora atual com fuso horário
    # Define por quanto tempo uma consulta é considerada "ativa" após seu início
    # (Ex: 1 hora de duração + 30 minutos de tolerância para entrar)
    janela_ativa = timedelta(hours=1, minutes=30)

    try:
        agendamentos_qs = None
        if hasattr(user, 'perfil_paciente'):
            perfil = user.perfil_paciente
            agendamentos_qs = Agendamento.objects.filter(paciente=perfil)
        elif hasattr(user, 'perfil_profissional'):
            perfil = user.perfil_profissional
            is_profissional = True
            agendamentos_qs = Agendamento.objects.filter(profissional=perfil)
        
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
        'agendamentos_ativos': agendamentos_ativos, # Novo contexto
        'agendamentos_passados': agendamentos_passados,
        'is_profissional': is_profissional,
    }
    return render(request, 'contas/meus_agendamentos.html', contexto)

# View para cancelar um agendamento (requer POST)
@login_required
@require_POST # Garante que esta view só pode ser acessada via POST
def cancelar_agendamento(request, agendamento_id):
    # Busca o agendamento específico ou retorna 404
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    user = request.user

    # Verifica se o usuário tem perfil e se é o paciente ou profissional do agendamento
    perfil_paciente_associado = hasattr(user, 'perfil_paciente') and agendamento.paciente == user.perfil_paciente
    perfil_profissional_associado = hasattr(user, 'perfil_profissional') and agendamento.profissional == user.perfil_profissional

    # Verifica se o usuário logado é o paciente OU o profissional deste agendamento
    if not (perfil_paciente_associado or perfil_profissional_associado):
        messages.error(request, "Você não tem permissão para cancelar este agendamento.")
        return redirect('contas:meus_agendamentos')

    # Verifica se o agendamento PODE ser cancelado (não está realizado ou já cancelado)
    if agendamento.status not in ['PENDENTE', 'CONFIRMADO']:
        messages.warning(request, f"Este agendamento não pode mais ser cancelado (Status: {agendamento.get_status_display()}).")
        return redirect('contas:meus_agendamentos')

    # Prepara informações para o email ANTES de mudar o status
    paciente_email = agendamento.paciente.user.email
    profissional_email = agendamento.profissional.user.email

    # Pega o nome completo OU o username se o nome completo for vazio (CORRIGIDO)
    paciente_full_name = agendamento.paciente.user.get_full_name()
    paciente_nome = paciente_full_name or agendamento.paciente.user.username

    profissional_full_name = agendamento.profissional.user.get_full_name()
    profissional_nome = profissional_full_name or agendamento.profissional.user.username

    data_hora_agendamento = agendamento.data_hora

    # Quem está cancelando?
    cancelado_por = "Paciente" if perfil_paciente_associado else "Profissional"
    # Quem deve receber a notificação?
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
                'cancelado_por': cancelado_por, # Informa quem cancelou
            }
            corpo_email_txt = render_to_string(template_txt, contexto_email)

            if email_destinatario: # Verifica se o destinatário tem email cadastrado
                send_mail(
                    assunto,
                    corpo_email_txt,
                    settings.DEFAULT_FROM_EMAIL,
                    [email_destinatario],
                    fail_silently=False, # Mude para True em produção se preferir
                )
            else:
                 messages.warning(request, "Agendamento cancelado, mas não foi possível notificar a outra parte (email não encontrado).")

        except Exception as e_mail:
            # Não impede o fluxo se o email falhar, mas avisa no log do servidor ou com mensagem
            print(f"Erro ao enviar email de cancelamento: {e_mail}") # Log simples para o console
            messages.warning(request, f"Agendamento cancelado, mas houve um erro ao enviar o email de notificação.")

    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao cancelar o agendamento: {e}")

    return redirect('contas:meus_agendamentos')


@login_required
@require_POST
def criar_agendamento(request, profissional_id, timestamp_str):
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

    # Revalidação de horário vago e no futuro (como antes)
    if Agendamento.objects.filter(profissional=profissional, data_hora=slot_datetime, status__in=['PENDENTE', 'CONFIRMADO']).exists():
        messages.error(request, "Desculpe, este horário foi agendado por outra pessoa. Por favor, escolha outro.")
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)
    if slot_datetime <= timezone.now():
        messages.error(request, "Não é possível agendar horários no passado.")
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)

    # Cria o Agendamento com status de pagamento pendente
    novo_agendamento = Agendamento.objects.create(
        paciente=perfil_paciente,
        profissional=profissional,
        data_hora=slot_datetime,
        status='PENDENTE',
        status_pagamento='PENDENTE'
    )
    
    try:
        # Cria um PaymentIntent no Stripe
        # O valor deve ser em centavos (ex: R$ 50,00 = 5000)
        valor_em_centavos = int(profissional.valor_consulta * 100)
        
        intent = stripe.PaymentIntent.create(
            amount=valor_em_centavos,
            currency='brl',
            metadata={'agendamento_id': novo_agendamento.id} # Guarda o ID do nosso agendamento no Stripe
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


# View para o profissional confirmar um agendamento pendente
@login_required
@require_POST # Apenas POST
def confirmar_agendamento(request, agendamento_id):
    user = request.user
    # Verifica se o usuário logado é um profissional
    if not hasattr(user, 'perfil_profissional'):
        messages.error(request, "Apenas profissionais podem confirmar agendamentos.")
        return redirect('contas:meus_agendamentos') # Ou para onde fizer sentido

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

        # ---- ENVIAR EMAIL PARA O PACIENTE ----
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
                [agendamento.paciente.user.email], # Email do PACIENTE
                fail_silently=False,
            )
        except Exception as e_mail:
            messages.warning(request, f"Agendamento confirmado, mas houve um erro ao notificar o paciente por email: {e_mail}")
        # ---- FIM DO ENVIO DE EMAIL ----

    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao confirmar o agendamento: {e}")

    return redirect('contas:meus_agendamentos')

# View para o profissional marcar um agendamento como realizado
@login_required
@require_POST # Apenas POST
def marcar_realizado(request, agendamento_id):
    user = request.user
    # Verifica se o usuário logado é um profissional
    if not hasattr(user, 'perfil_profissional'):
        messages.error(request, "Apenas profissionais podem marcar agendamentos como realizados.")
        return redirect('contas:meus_agendamentos')

    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    perfil_profissional = user.perfil_profissional

    # Verifica se o profissional logado é o profissional deste agendamento
    if agendamento.profissional != perfil_profissional:
        messages.error(request, "Você não tem permissão para alterar este agendamento.")
        return redirect('contas:meus_agendamentos')

    # Verifica se o agendamento está CONFIRMADO e se já passou (ou está acontecendo)
    # Usar <= permite marcar como realizado mesmo que tenha acabado de começar
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



# @login_required
# def calendario_profissional(request):
#     user = request.user
#     if not hasattr(user, 'perfil_profissional'):
#         messages.error(request, "Apenas profissionais podem acessar esta página.")
#         return redirect('contas:index')

#     perfil = user.perfil_profissional
#     tz_padrao = timezone.get_default_timezone()
#     agora = timezone.now()
#     hoje = timezone.localdate() # Necessário para o startRecur e lógica de período

#     # Período de visualização para o calendário do profissional
#     # Buscamos um pouco do passado para contexto de agendamentos e um período razoável no futuro
#     data_inicio_periodo_geral = agora - timedelta(days=30) 
#     data_fim_periodo_geral = agora + timedelta(days=90)  

#     # --- Busca de Dados Relevantes ---
#     # Busca TODAS as regras de disponibilidade (semanais e específicas)
#     todas_as_regras_disponibilidade = perfil.regras_disponibilidade.all().order_by('data_hora_inicio_especifica', 'hora_inicio_recorrente')
    
#     # Agendamentos (todos os status para visualização do profissional)
#     agendamentos_objs = perfil.agendamentos.filter(
#         data_hora__gte=data_inicio_periodo_geral, data_hora__lt=data_fim_periodo_geral
#     )
    
#     # --- Processamento para Eventos FullCalendar ---
#     all_events = [] # Lista Python de dicionários
#     duracao_consulta_padrao = timedelta(hours=1) # Duração padrão para agendamentos
    
#     # Cores alinhadas com a Identidade Visual "Hope Saúde"
#     cor_disponivel_bloco = '#5cb85c' # Verde "calmo" para disponibilidade (ajuste se tiver um no manual)
#                                      # O manual sugere Verde Sálvia (#B2C2B3) para detalhes/fundos.
#                                      # Para blocos de disponibilidade, um verde mais claro mas sólido pode ser bom.
#                                      # Se usar --hope-verde-salvia (#B2C2B3), o texto precisará ser escuro.
#     borda_cor_disponivel_bloco = '#4cae4c' # Tom ligeiramente mais escuro para borda
#     texto_cor_disponivel = '#FFFFFF' # Texto branco para contraste com o verde acima

#     # cor_bloqueio_fundo = '#e9ecef' # Removido - Não há mais BloqueioTempo

#     # 1. & 2. Processar Regras de Disponibilidade (Semanal e Específica)
#     for regra in todas_as_regras_disponibilidade:
#         if regra.tipo_regra == 'SEMANAL':
#             if regra.dia_semana is not None and regra.hora_inicio_recorrente and regra.hora_fim_recorrente:
#                 fc_day = (regra.dia_semana + 1) % 7 # Converte dia Python (Mon=0) para FullCalendar (Sun=0)
#                 all_events.append({
#                     'title': 'Disponível', 
#                     'groupId': f'regra_disp_semanal_{regra.id}', # Para identificar o grupo de recorrência
#                     'daysOfWeek': [ fc_day ], 
#                     'startTime': regra.hora_inicio_recorrente.strftime('%H:%M:%S'),
#                     'endTime': regra.hora_fim_recorrente.strftime('%H:%M:%S'), 
#                     'display': 'block', # Para ser um bloco visível e mais proeminente
#                     'color': cor_disponivel_bloco, 
#                     'borderColor': borda_cor_disponivel_bloco,
#                     'textColor': texto_cor_disponivel,
#                     'extendedProps': {'tipo': 'disponibilidade_semanal', 'id_original': regra.id}
#                     # 'startRecur': hoje.isoformat(), # Para iniciar a recorrência a partir de hoje
#                 })
#         elif regra.tipo_regra == 'ESPECIFICA':
#             if regra.data_hora_inicio_especifica and regra.data_hora_fim_especifica:
#                 start_dt = regra.data_hora_inicio_especifica.astimezone(tz_padrao)
#                 end_dt = regra.data_hora_fim_especifica.astimezone(tz_padrao)
                
#                 # Adiciona apenas se o período específico interceptar o período geral de visualização
#                 if start_dt < data_fim_periodo_geral and end_dt > data_inicio_periodo_geral:
#                     all_events.append({
#                         'title': 'Disponível', 
#                         'start': start_dt.isoformat(),
#                         'end': end_dt.isoformat(), # Mostra o bloco específico com sua duração total
#                         'color': cor_disponivel_bloco, 
#                         'borderColor': borda_cor_disponivel_bloco,
#                         'textColor': texto_cor_disponivel,
#                         'id': f'regra_disp_esp_{regra.id}',
#                         'extendedProps': {'tipo': 'regra_disponibilidade_especifica', 'id_original': regra.id}
#                     })

#     # Lógica de AGRUPAR Regras de Disponibilidade Específicas Contíguas (VISUALMENTE)
#     # Esta lógica é para a VIEW do profissional, para que ele veja blocos contínuos.
#     # A view do PACIENTE (perfil_profissional_detail) quebra em slots agendáveis.
#     # (Mantida da Resposta #151, com o título ajustado)
    
#     # Primeiro, separe os eventos de disponibilidade específica dos outros para o agrupamento
#     eventos_disp_especifica_para_agrupar = [e for e in all_events if e.get('extendedProps', {}).get('tipo') == 'disponibilidade_especifica']
#     outros_eventos = [e for e in all_events if e.get('extendedProps', {}).get('tipo') != 'disponibilidade_especifica']
    
#     all_events_final_agrupado = list(outros_eventos) # Começa com os que não são para agrupar

#     if eventos_disp_especifica_para_agrupar:
#         # Ordena por data de início para garantir o agrupamento correto
#         eventos_disp_especifica_para_agrupar.sort(key=lambda x: x['start'])
        
#         merged_specific_slots = []
#         current_merged_event = None

#         for evento_esp in eventos_disp_especifica_para_agrupar:
#             start_dt_obj = datetime.fromisoformat(evento_esp['start'])
#             end_dt_obj = datetime.fromisoformat(evento_esp['end'])

#             if current_merged_event is None:
#                 current_merged_event = {
#                     'title': 'Disponível', # Título para o bloco agrupado
#                     'start_obj': start_dt_obj, # Guardar como objeto datetime para comparação
#                     'end_obj': end_dt_obj,
#                     'ids_originais': evento_esp['extendedProps']['id_original'], # Pode ser uma lista se já agrupado, ou um int
#                     'color': evento_esp['color'], # Mantém a cor
#                     'borderColor': evento_esp['borderColor'],
#                     'textColor': evento_esp['textColor']
#                 }
#                 # Garante que ids_originais seja sempre uma lista
#                 if not isinstance(current_merged_event['ids_originais'], list):
#                     current_merged_event['ids_originais'] = [current_merged_event['ids_originais']]

#             elif start_dt_obj == current_merged_event['end_obj']: # Contíguo
#                 current_merged_event['end_obj'] = end_dt_obj # Estende o fim
#                 # Adiciona o ID da regra original se não for uma lista já (caso de evento não agrupado anteriormente)
#                 if isinstance(evento_esp['extendedProps']['id_original'], list):
#                     current_merged_event['ids_originais'].extend(evento_esp['extendedProps']['id_original'])
#                 else:
#                     current_merged_event['ids_originais'].append(evento_esp['extendedProps']['id_original'])
#                 # Remove duplicatas de IDs se houver (improvável, mas seguro)
#                 current_merged_event['ids_originais'] = sorted(list(set(current_merged_event['ids_originais'])))
#             else: # Quebra de continuidade
#                 if current_merged_event:
#                     all_events_final_agrupado.append({
#                         'title': current_merged_event['title'],
#                         'start': current_merged_event['start_obj'].isoformat(),
#                         'end': current_merged_event['end_obj'].isoformat(),
#                         'color': current_merged_event['color'],
#                         'borderColor': current_merged_event['borderColor'],
#                         'textColor': current_merged_event['textColor'],
#                         'id': f'regra_disp_esp_agrupada_{"_".join(map(str, current_merged_event["ids_originais"]))}',
#                         'extendedProps': {'tipo': 'disponibilidade_especifica_agrupada', 'ids_originais': current_merged_event['ids_originais']}
#                     })
#                 current_merged_event = {
#                     'title': 'Disponível', 'start_obj': start_dt_obj, 'end_obj': end_dt_obj,
#                     'ids_originais': [evento_esp['extendedProps']['id_original']] if not isinstance(evento_esp['extendedProps']['id_original'], list) else evento_esp['extendedProps']['id_original'],
#                     'color': evento_esp['color'], 'borderColor': evento_esp['borderColor'], 'textColor': evento_esp['textColor']
#                 }
        
#         if current_merged_event: # Adiciona o último bloco agrupado
#             all_events_final_agrupado.append({
#                 'title': current_merged_event['title'],
#                 'start': current_merged_event['start_obj'].isoformat(),
#                 'end': current_merged_event['end_obj'].isoformat(),
#                 'color': current_merged_event['color'],
#                 'borderColor': current_merged_event['borderColor'],
#                 'textColor': current_merged_event['textColor'],
#                 'id': f'regra_disp_esp_agrupada_{"_".join(map(str, current_merged_event["ids_originais"]))}',
#                 'extendedProps': {'tipo': 'disponibilidade_especifica_agrupada', 'ids_originais': current_merged_event['ids_originais']}
#             })
#     else: # Se não houver eventos específicos para agrupar, apenas usa os outros (semanais)
#         all_events_final_agrupado = list(all_events) # all_events aqui conteria apenas os semanais


#     # Adiciona os Agendamentos (eles sobreporão visualmente as disponibilidades)
#     for ag in agendamentos_objs:
#         paciente_full_name = ag.paciente.user.get_full_name()
#         paciente_display_name = paciente_full_name or ag.paciente.user.username
        
#         cor_agendamento = '#0d6efd'; borda_cor_agendamento = '#0a58ca'; texto_cor_agendamento = 'white'
#         if ag.status == 'PENDENTE': cor_agendamento = '#ffc107'; borda_cor_agendamento = '#cc9a06'; texto_cor_agendamento = '#212529'
#         elif ag.status == 'REALIZADO': cor_agendamento = '#198754'; borda_cor_agendamento = '#146c43'; texto_cor_agendamento = 'white'
#         elif ag.status == 'CANCELADO': cor_agendamento = '#dc3545'; borda_cor_agendamento = '#b02a37'; texto_cor_agendamento = 'white'

#         all_events_final_agrupado.append({
#             'title': f"Consulta: {paciente_display_name} ({ag.get_status_display()})",
#             'start': ag.data_hora.isoformat(), 
#             'end': (ag.data_hora + duracao_consulta_padrao).isoformat(),
#             'color': cor_agendamento, 
#             'borderColor': borda_cor_agendamento,
#             'textColor': texto_cor_agendamento,
#             'id': f'ag_{ag.id}',
#             'extendedProps': {'tipo': 'agendamento', 'id_original': ag.id, 'status': ag.status}
#         })
    
#     # --- Contexto Final ---
#     contexto = {
#         # Passa a LISTA PYTHON FINAL (com específicos agrupados) diretamente.
#         'calendar_events_data': all_events_final_agrupado,
#     }
#     return render(request, 'contas/calendario_profissional.html', contexto)


@login_required
def calendario_profissional(request):
    # O decorator @login_required já garante que request.user existe.
    # O ideal é adicionar um teste para garantir que o usuário é um profissional.
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


# @login_required
# def gerenciar_regras_disponibilidade(request):
#     user = request.user
#     if not hasattr(user, 'perfil_profissional'):
#         messages.error(request, "Esta página é acessível apenas para profissionais.")
#         return redirect('contas:index')

#     perfil_profissional = user.perfil_profissional
#     form_erros = None # Para guardar erros do formulário em caso de POST falho

#     if request.method == 'POST':
#         form = RegraDisponibilidadeForm(request.POST)
#         if form.is_valid():
#             try:
#                 nova_regra = form.save(commit=False)
#                 nova_regra.profissional = perfil_profissional
#                 nova_regra.save()
#                 messages.success(request, "Nova regra de disponibilidade adicionada com sucesso!")
#                 return redirect('contas:gerenciar_regras_disponibilidade') # Redireciona para limpar o form
#             except IntegrityError: # Para o caso de alguma restrição de banco (ex: unique_together se adicionada)
#                 messages.error(request, "Não foi possível salvar. Verifique se este horário já não existe ou há um conflito.")
#                 form_erros = form # Passa o formulário com erros para ser exibido
#             except ValidationError as e: # Captura ValidationError do clean() do modelo, se não pego pelo form.is_valid()
#                 messages.error(request, "Erro de validação ao salvar a regra.")
#                 # Adicionar erros do modelo ao formulário para exibição
#                 # form.add_error(None, e) # Adiciona como non-field error
#                 # Ou iterar sobre e.message_dict para adicionar a campos específicos se possível
#                 for field, field_errors in e.message_dict.items():
#                     for error in field_errors:
#                         if field == '__all__': # Erro geral do modelo
#                             form.add_error(None, error)
#                         else:
#                             form.add_error(field, error) # Adiciona ao campo específico
#                 form_erros = form
#             except Exception as e:
#                  messages.error(request, f"Ocorreu um erro inesperado: {e}")
#                  form_erros = form
#         else:
#             messages.error(request, "Por favor, corrija os erros no formulário abaixo.")
#             form_erros = form # Passa o formulário com os erros de validação do form

#     # Se GET, ou se o POST falhou e form_erros foi definido
#     if form_erros:
#         form_para_template = form_erros
#     else:
#         form_para_template = RegraDisponibilidadeForm() # Formulário vazio para GET

#     # Busca todas as regras existentes do profissional para listar
#     regras_existentes = perfil_profissional.regras_disponibilidade.all().order_by('tipo_regra', 'dia_semana', 'data_hora_inicio_especifica', 'hora_inicio_recorrente')

#     contexto = {
#         'form': form_para_template,
#         'regras_disponibilidade': regras_existentes,
#     }
#     return render(request, 'contas/gerenciar_regras_disponibilidade.html', contexto)


@login_required
@require_POST # Exige que a requisição seja POST para segurança
def excluir_regra_disponibilidade(request, regra_id):
    user = request.user
    # Verifica se o usuário é um profissional
    if not hasattr(user, 'perfil_profissional'):
        messages.error(request, "Ação não permitida.")
        # Idealmente, redirecionar para uma página de erro ou a inicial
        return redirect('contas:index')

    # Busca a regra de disponibilidade específica ou retorna 404
    regra = get_object_or_404(RegraDisponibilidade, pk=regra_id)

    # Verifica se a regra pertence ao profissional logado
    if regra.profissional != user.perfil_profissional:
        messages.error(request, "Você não tem permissão para excluir esta regra de disponibilidade.")
        return redirect('contas:gerenciar_regras_disponibilidade')

    # Se tudo estiver OK, exclui a regra
    try:
        tipo_regra_display = regra.get_tipo_regra_display()
        detalhes_regra = str(regra) # Pega a representação em string para a mensagem
        regra.delete()
        messages.success(request, f"Regra de disponibilidade ({detalhes_regra}) excluída com sucesso.")
    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao excluir a regra de disponibilidade: {e}")

    return redirect('contas:gerenciar_regras_disponibilidade')


@login_required
def calendario_profissional(request):
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        # ... (tratamento de erro como antes) ...
        messages.error(request, "Apenas profissionais podem acessar esta página.")
        return redirect('contas:index')

    perfil = user.perfil_profissional
    tz_padrao = timezone.get_default_timezone()
    agora = timezone.now()
    hoje = timezone.localdate() # Usado para lógica de recorrência semanal

    data_inicio_periodo_geral = agora - timedelta(days=30)
    data_fim_periodo_geral = agora + timedelta(days=90)

    # --- Busca de Dados Relevantes ---
    todas_as_regras_disponibilidade_qs = perfil.regras_disponibilidade.all().order_by('data_hora_inicio_especifica', 'hora_inicio_recorrente')
    
    agendamentos_objs = perfil.agendamentos.filter(
        data_hora__gte=data_inicio_periodo_geral, data_hora__lt=data_fim_periodo_geral
    )
    
    all_events = []
    duracao_consulta = timedelta(hours=1)
    
    cor_disponivel_bloco = '#5cb85c' 
    borda_cor_disponivel_bloco = '#4cae4c'

    # 1. Disponibilidade Semanal Recorrente (permanece como eventos recorrentes separados)
    for regra in todas_as_regras_disponibilidade_qs:
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

    # 2. Processar e AGRUPAR Regras de Disponibilidade Específicas Contíguas
    regras_especificas = todas_as_regras_disponibilidade_qs.filter(tipo_regra='ESPECIFICA').order_by('data_hora_inicio_especifica')
    
    merged_specific_slots = []
    current_merged_event = None

    for regra in regras_especificas:
        if regra.data_hora_inicio_especifica and regra.data_hora_fim_especifica:
            start_dt = regra.data_hora_inicio_especifica.astimezone(tz_padrao)
            end_dt = regra.data_hora_fim_especifica.astimezone(tz_padrao)

            # Considera apenas se o período intercepta a visualização geral
            if not (start_dt < data_fim_periodo_geral and end_dt > data_inicio_periodo_geral):
                continue

            if current_merged_event is None: # Primeiro evento do grupo (ou novo grupo)
                current_merged_event = {
                    'title': 'Disponível',
                    'start': start_dt, # Mantém como objeto datetime por enquanto
                    'end': end_dt,     # Mantém como objeto datetime
                    'ids_originais': [regra.id] # Lista de IDs das regras originais agrupadas
                }
            # Se a regra atual começa exatamente onde o bloco agrupado anterior terminou
            elif start_dt == current_merged_event['end']:
                current_merged_event['end'] = end_dt # Estende o fim do bloco agrupado
                current_merged_event['ids_originais'].append(regra.id)
            else: # Há um espaço ou sobreposição não contígua, finaliza o bloco anterior e começa um novo
                if current_merged_event:
                    merged_specific_slots.append(current_merged_event)
                current_merged_event = {
                    'title': 'Disponível',
                    'start': start_dt, 'end': end_dt,
                    'ids_originais': [regra.id]
                }
    
    # Adiciona o último bloco agrupado, se existir
    if current_merged_event:
        merged_specific_slots.append(current_merged_event)

    # Converte os blocos específicos agrupados para o formato do FullCalendar
    for slot_agrupado in merged_specific_slots:
        all_events.append({
            'title': slot_agrupado['title'],
            'start': slot_agrupado['start'].isoformat(),
            'end': slot_agrupado['end'].isoformat(),
            'color': cor_disponivel_bloco,
            'borderColor': borda_cor_disponivel_bloco,
            'id': f'regra_disp_esp_agrupada_{"_".join(map(str, slot_agrupado["ids_originais"]))}',
            # Guardamos todos os IDs originais caso precisemos para edição/exclusão
            'extendedProps': {'tipo': 'disponibilidade_especifica_agrupada', 'ids_originais': slot_agrupado['ids_originais']}
        })

    # 3. Agendamentos (como antes)
    for ag in agendamentos_objs:
        # ... (lógica para nome do paciente e cores do agendamento como antes) ...
        paciente_full_name = ag.paciente.user.get_full_name()
        paciente_display_name = paciente_full_name or ag.paciente.user.username
        cor_agendamento = '#0d6efd'; borda_cor_agendamento = '#0a58ca'
        if ag.status == 'PENDENTE': cor_agendamento = '#ffc107'; borda_cor_agendamento = '#cc9a06'
        elif ag.status == 'REALIZADO': cor_agendamento = '#198754'; borda_cor_agendamento = '#146c43'
        elif ag.status == 'CANCELADO': cor_agendamento = '#dc3545'; borda_cor_agendamento = '#b02a37'
        all_events.append({
            'title': f"Consulta: {paciente_display_name} ({ag.get_status_display()})",
            'start': ag.data_hora.isoformat(), 
            'end': (ag.data_hora + duracao_consulta).isoformat(),
            'color': cor_agendamento, 
            'borderColor': borda_cor_agendamento,
            'id': f'ag_{ag.id}',
            'extendedProps': {'tipo': 'agendamento', 'id_original': ag.id, 'status': ag.status}
        })
    
    # ... (contexto e render como antes) ...
    contexto = {
        'calendar_events_data': all_events,
    }
    return render(request, 'contas/calendario_profissional.html', contexto)


# Em contas/views.py
# (outros imports e views permanecem como estão)

@login_required
@require_POST
def api_criar_disp_avulsa(request):
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        return api_error_response(
            message='Apenas profissionais podem adicionar disponibilidade.',
            status_code=403
        )

    try:
        data = json.loads(request.body)
        inicio_str = data.get('data_hora_inicio_especifica')
        fim_str = data.get('data_hora_fim_especifica')

        if not inicio_str or not fim_str:
            return api_error_response(message='Datas de início e fim são obrigatórias.')

        # novo_inicio = datetime.fromisoformat(inicio_str)
        # novo_fim = datetime.fromisoformat(fim_str)
        novo_inicio = parser.parse(inicio_str)
        novo_fim = parser.parse(fim_str)

        if novo_inicio.tzinfo is None:
            novo_inicio = novo_inicio.replace(tzinfo=timezone.utc)
        if novo_fim.tzinfo is None:
            novo_fim = novo_fim.replace(tzinfo=timezone.utc)

        perfil_profissional = user.perfil_profissional

        # --- LÓGICA DE FUSÃO ATUALIZADA ---

        # Busca por regras adjacentes em ambos os lados
        regra_anterior = RegraDisponibilidade.objects.filter(
            profissional=perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_fim_especifica=novo_inicio
        ).first()

        regra_posterior = RegraDisponibilidade.objects.filter(
            profissional=perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=novo_fim
        ).first()

        # Cenário 1: Fusão Tripla (encontrou regras em ambos os lados)
        if regra_anterior and regra_posterior:
            # Estende a regra anterior para abranger o fim da regra posterior
            regra_anterior.data_hora_fim_especifica = regra_posterior.data_hora_fim_especifica
            regra_anterior.full_clean()
            regra_anterior.save()
            
            # Deleta a regra posterior, que agora foi "absorvida"
            regra_posterior.delete()
            
            return api_success_response(
                data={'message': 'Disponibilidades unificadas com sucesso!'},
                status_code=200
            )

        # Cenário 2: Extensão para a frente (encontrou apenas regra anterior)
        if regra_anterior:
            regra_anterior.data_hora_fim_especifica = novo_fim
            regra_anterior.full_clean()
            regra_anterior.save()
            return api_success_response(
                data={'message': 'Disponibilidade estendida com sucesso!'},
                status_code=200
            )

        # Cenário 3: Extensão para trás (encontrou apenas regra posterior)
        if regra_posterior:
            regra_posterior.data_hora_inicio_especifica = novo_inicio
            regra_posterior.full_clean()
            regra_posterior.save()
            return api_success_response(
                data={'message': 'Disponibilidade estendida com sucesso!'},
                status_code=200
            )

        # Cenário 4: Nenhuma regra adjacente, cria uma nova
        nova_regra = RegraDisponibilidade(
            profissional=perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=novo_inicio,
            data_hora_fim_especifica=novo_fim
        )
        nova_regra.full_clean()
        nova_regra.save()
        
        return api_success_response(
            data={'message': 'Disponibilidade específica criada com sucesso!'},
            status_code=201
        )

    except json.JSONDecodeError:
        return api_error_response(message='Dados JSON inválidos na requisição.')
    except ValidationError as e:
        error_message = e.messages[0] if e.messages else "Erro de validação desconhecido."
        return api_error_response(message=error_message)
    except Exception as e:
        print(f"Erro inesperado em api_criar_disp_avulsa: {e}")
        return api_error_response(
            message='Ocorreu um erro interno ao criar a disponibilidade.',
            status_code=500
        )
    

@login_required
@require_POST
def api_editar_regra_disponibilidade(request, regra_id):
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        return api_error_response(message='Apenas profissionais podem editar disponibilidades.', status_code=403)

    try:
        regra = RegraDisponibilidade.objects.get(pk=regra_id, profissional=user.perfil_profissional)
    except RegraDisponibilidade.DoesNotExist:
        return api_error_response(message='Regra de disponibilidade não encontrada ou você não tem permissão.', status_code=404)

    if regra.tipo_regra != 'ESPECIFICA':
        return api_error_response(message='Apenas disponibilidades específicas podem ser editadas por esta interface.')

    try:
        data = json.loads(request.body.decode('utf-8'))
        inicio_str = data.get('data_hora_inicio_especifica')
        fim_str = data.get('data_hora_fim_especifica')

        if not inicio_str or not fim_str:
            return api_error_response(message='Datas de início e fim são obrigatórias.')

        regra.data_hora_inicio_especifica = datetime.fromisoformat(inicio_str.replace('Z', '+00:00'))
        regra.data_hora_fim_especifica = datetime.fromisoformat(fim_str.replace('Z', '+00:00'))

        regra.full_clean()
        regra.save()

        return api_success_response(data={'message': 'Disponibilidade específica atualizada com sucesso!'})

    except (json.JSONDecodeError, ValueError):
        return api_error_response(message='Dados ou formato de data inválidos na requisição.')
    except ValidationError as e:
        error_message = next(iter(e.message_dict.values()))[0] if e.message_dict else "Erro de validação."
        return api_error_response(message=error_message)
    except Exception as e:
        print(f"Erro inesperado em api_editar_regra_disponibilidade: {e}")
        return api_error_response(message='Ocorreu um erro interno ao atualizar a disponibilidade.', status_code=500)



@login_required
@require_POST
def api_excluir_regras_disponibilidade_lista(request):
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        return api_error_response(message='Ação não permitida.', status_code=403)

    try:
        data = json.loads(request.body.decode('utf-8'))
        ids_para_excluir = data.get('ids')

        if not ids_para_excluir or not isinstance(ids_para_excluir, list) or not all(isinstance(id_val, int) for id_val in ids_para_excluir):
            return api_error_response(message='Lista de IDs inválida ou não fornecida.')

        regras_a_excluir = RegraDisponibilidade.objects.filter(
            pk__in=ids_para_excluir,
            profissional=user.perfil_profissional,
            tipo_regra='ESPECIFICA'
        )

        count_excluidas = regras_a_excluir.count()

        if count_excluidas == 0 and len(ids_para_excluir) > 0:
            return api_error_response(
                message='Nenhuma regra válida para exclusão foi encontrada ou você não tem permissão.',
                status_code=404
            )

        if count_excluidas > 0:
            regras_a_excluir.delete()

        return api_success_response(
            data={'message': f'{count_excluidas} regra(s) de disponibilidade específica excluída(s) com sucesso.'}
        )

    except json.JSONDecodeError:
        return api_error_response(message='Dados JSON inválidos.')
    except Exception as e:
        print(f"Erro em api_excluir_regras_disponibilidade_lista: {e}")
        return api_error_response(
            message='Erro interno ao excluir regras de disponibilidade.',
            status_code=500
        )


@login_required
def api_obter_ou_criar_sala_video(request, agendamento_id):
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    user = request.user
    agora = timezone.now()

    is_paciente_do_agendamento = hasattr(user, 'perfil_paciente') and agendamento.paciente == user.perfil_paciente
    is_profissional_do_agendamento = hasattr(user, 'perfil_profissional') and agendamento.profissional == user.perfil_profissional

    if not (is_paciente_do_agendamento or is_profissional_do_agendamento):
        return api_error_response(message='Você não tem permissão para acessar esta sala de vídeo.', status_code=403)

    if agendamento.status != 'CONFIRMADO':
        return api_error_response(message='Esta consulta não está confirmada e não pode ser iniciada.')

    horario_inicio_consulta = agendamento.data_hora
    horario_fim_consulta_estimado = horario_inicio_consulta + timedelta(hours=1)
    
    # Validações de horário
    if agora < (horario_inicio_consulta - timedelta(minutes=30)):
        return api_error_response(message='Ainda é muito cedo para entrar nesta consulta. Tente mais perto do horário agendado.')
    if agora > (horario_fim_consulta_estimado + timedelta(minutes=30)):
        return api_error_response(message='O tempo para esta consulta já expirou.')

    # Tenta obter ou criar a sala
    try:
        # Nota: a lógica interna de criação/obtenção da sala foi mantida como estava
        room_url_final_com_token = agendamento.obter_ou_criar_url_sala_com_token(
            user=user,
            is_owner=is_profissional_do_agendamento
        )
        return api_success_response(data={'room_url': room_url_final_com_token})
    except Exception as e:
        # A lógica de tratamento de erro já imprime no console.
        # Agora, ela também retornará uma resposta padronizada.
        return api_error_response(message=str(e), status_code=500)
    

@login_required
def processar_pagamento(request, agendamento_id):
    # Configura a chave da API do Stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id, paciente__user=request.user)

    # Se o agendamento já foi pago, redireciona para a página de agendamentos
    if agendamento.status_pagamento == 'PAGO':
        messages.info(request, "Este agendamento já foi pago.")
        return redirect('contas:meus_agendamentos')
    
    try:
        # Recupera o PaymentIntent do Stripe para obter o client_secret
        intent = stripe.PaymentIntent.retrieve(agendamento.pagamento_id)
        
        contexto = {
            'agendamento': agendamento,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'client_secret': intent.client_secret,
        }
        return render(request, 'contas/processar_pagamento.html', contexto)

    except Exception as e:
        messages.error(request, f"Não foi possível carregar a página de pagamento: {e}")
        return redirect('contas:meus_agendamentos')
    

@csrf_exempt # Isenta esta view da verificação de CSRF, pois a requisição vem de um serviço externo
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Payload inválido
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Assinatura inválida
        return HttpResponse(status=400)

    # Lida com o evento 'payment_intent.succeeded'
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object'] # contém o PaymentIntent
        
        # Busca o ID do nosso agendamento que guardamos nos metadados
        agendamento_id = payment_intent['metadata'].get('agendamento_id')
        
        try:
            agendamento = Agendamento.objects.get(id=agendamento_id)
            
            # Atualiza o status do pagamento e do agendamento
            agendamento.status_pagamento = 'PAGO'
            agendamento.status = 'CONFIRMADO' # Muda de 'Pendente' para 'Confirmado'
            agendamento.save()
            
            print(f"SUCESSO: Agendamento {agendamento_id} atualizado para PAGO e CONFIRMADO.")
            
            # Aqui você pode adicionar o envio de email de confirmação para paciente e profissional

        except Agendamento.DoesNotExist:
            print(f"ERRO no webhook: Agendamento com id {agendamento_id} não encontrado.")
            return HttpResponse(status=404)
        
    else:
        # Lida com outros tipos de evento, se necessário
        print(f"Evento não tratado: {event['type']}")

    # Retorna uma resposta 200 para o Stripe para confirmar o recebimento
    return HttpResponse(status=200)


@login_required
@require_POST
def api_submeter_avaliacao(request):
    # Permissão: apenas pacientes podem avaliar
    if not hasattr(request.user, 'perfil_paciente'):
        return api_error_response(message="Apenas pacientes podem enviar avaliações.", status_code=403)

    try:
        data = json.loads(request.body)
        agendamento_id = data.get('agendamento_id')
        nota = data.get('nota')
        comentario = data.get('comentario', '') # Comentário é opcional

        if not all([agendamento_id, nota]):
            return api_error_response(message="Dados incompletos para submeter a avaliação.")

        # Validação: O agendamento deve existir e pertencer ao paciente logado
        agendamento = get_object_or_404(Agendamento, pk=agendamento_id, paciente=request.user.perfil_paciente)

        # Lógica de Negócio:
        # 1. Só pode avaliar agendamentos realizados
        if agendamento.status != 'REALIZADO':
            return api_error_response(message="Só é possível avaliar consultas que já foram realizadas.")
        
        # 2. Só pode avaliar uma vez (o OneToOneField no modelo já garante isso no banco,
        # mas uma verificação aqui fornece uma mensagem de erro melhor)
        if hasattr(agendamento, 'avaliacao'):
            return api_error_response(message="Este agendamento já foi avaliado.")

        # Cria a nova avaliação
        nova_avaliacao = Avaliacao(
            agendamento=agendamento,
            avaliador=agendamento.paciente,
            avaliado=agendamento.profissional,
            nota=int(nota),
            comentario=comentario
        )
        
        # Roda as validações do modelo (ex: nota entre 1 e 5)
        nova_avaliacao.full_clean()
        nova_avaliacao.save()
        
        return api_success_response(
            data={'message': 'Avaliação enviada com sucesso!'},
            status_code=201 # 201 Created
        )

    except Agendamento.DoesNotExist:
        return api_error_response(message="Agendamento não encontrado.", status_code=404)
    except (json.JSONDecodeError, ValueError, TypeError):
        return api_error_response(message="Dados inválidos ou em formato incorreto.")
    except ValidationError as e:
        # Converte o dicionário de erros de validação em uma mensagem amigável
        error_message = next(iter(e.message_dict.values()))[0] if e.message_dict else "Erro de validação."
        return api_error_response(message=error_message)
    except Exception as e:
        print(f"Erro inesperado em api_submeter_avaliacao: {e}")
        return api_error_response(message="Ocorreu um erro interno.", status_code=500)
    

@login_required
def sala_videochamada(request, agendamento_id):
    """
    Renderiza a página que irá hospedar a videochamada embutida.
    """
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    user = request.user

    # Validação de permissão: apenas o paciente ou o profissional do agendamento podem entrar.
    is_paciente_do_agendamento = hasattr(user, 'perfil_paciente') and agendamento.paciente == user.perfil_paciente
    is_profissional_do_agendamento = hasattr(user, 'perfil_profissional') and agendamento.profissional == user.perfil_profissional

    if not (is_paciente_do_agendamento or is_profissional_do_agendamento):
        messages.error(request, "Você não tem permissão para acessar esta sala.")
        return redirect('contas:meus_agendamentos')

    # Validação de status: A consulta deve estar confirmada.
    if agendamento.status != 'CONFIRMADO':
        messages.error(request, "Esta consulta não está confirmada e a sala de vídeo não pode ser acessada.")
        return redirect('contas:meus_agendamentos')

    contexto = {
        'agendamento': agendamento,
    }
    return render(request, 'contas/sala_videochamada.html', contexto)