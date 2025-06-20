# contas/views.py

from datetime import time, timedelta, date, datetime, timezone as dt_timezone # Importa timedelta e date
import requests # Para fazer chamadas HTTP à API do Daily.co
import stripe
import json # Importa json
from django.core.exceptions import ValidationError, ObjectDoesNotExist
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
from typing import TYPE_CHECKING
import stripe.error
if TYPE_CHECKING:
    from .models import PerfilProfissional, PerfilPaciente, Especialidade, Agendamento, RegraDisponibilidade

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
    profissionais_queryset = PerfilProfissional.objects.all().order_by('user__first_name')  # type: ignore

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
            Q(user__first_name__icontains=query) |  # type: ignore
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

    todas_especialidades = Especialidade.objects.all()  # type: ignore

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
                PerfilPaciente.objects.create(user=user)  # type: ignore
            elif tipo_conta == 'PROFISSIONAL':
                # Cria o perfil profissional (campos obrigatórios agora são opcionais no BD)
                PerfilProfissional.objects.create(user=user)  # type: ignore

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
        perfil_paciente = user.perfil_paciente
        contexto['perfil_paciente'] = perfil_paciente
    except ObjectDoesNotExist:
        pass

    try:
        perfil_profissional = user.perfil_profissional
        contexto['perfil_profissional'] = perfil_profissional
    except PerfilProfissional.DoesNotExist:  # type: ignore
        pass # Se não for profissional, não faz nada aqui

    # Verifica se algum perfil foi encontrado (deve acontecer se o registro funcionou)
    if 'perfil_paciente' not in contexto and 'perfil_profissional' not in contexto:
        # Situação inesperada: usuário logado sem perfil.
        # Poderíamos redirecionar para completar o perfil ou mostrar uma mensagem.
        # Por enquanto, vamos adicionar uma mensagem de erro simples no contexto.
        contexto['erro_perfil'] = "Não foi possível encontrar um perfil associado à sua conta."

    # Renderiza um template único para "meu perfil"
    return render(request, 'contas/meu_perfil.html', contexto)


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
            novo_inicio = novo_inicio.replace(tzinfo=timezone.get_default_timezone())
        if novo_fim.tzinfo is None:
            novo_fim = novo_fim.replace(tzinfo=timezone.get_default_timezone())

        perfil_profissional = user.perfil_profissional

        # --- LÓGICA DE FUSÃO ATUALIZADA ---

        # Busca por regras adjacentes em ambos os lados
        regra_anterior = RegraDisponibilidade.objects.filter(  # type: ignore
            profissional=perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_fim_especifica=novo_inicio
        ).first()

        regra_posterior = RegraDisponibilidade.objects.filter(  # type: ignore
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
        regra = RegraDisponibilidade.objects.get(pk=regra_id, profissional=user.perfil_profissional)  # type: ignore
    except Exception:
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

        regras_a_excluir = RegraDisponibilidade.objects.filter(  # type: ignore
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
    except Exception:
        # Assinatura inválida
        return HttpResponse(status=400)

    # Lida com o evento 'payment_intent.succeeded'
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object'] # contém o PaymentIntent
        
        # Busca o ID do nosso agendamento que guardamos nos metadados
        agendamento_id = payment_intent['metadata'].get('agendamento_id')
        
        try:
            agendamento = Agendamento.objects.get(id=agendamento_id)  # type: ignore
            
            # Atualiza o status do pagamento e do agendamento
            agendamento.status_pagamento = 'PAGO'
            agendamento.status = 'CONFIRMADO' # Muda de 'Pendente' para 'Confirmado'
            agendamento.save()
            
            print(f"SUCESSO: Agendamento {agendamento_id} atualizado para PAGO e CONFIRMADO.")
            
            # Aqui você pode adicionar o envio de email de confirmação para paciente e profissional

        except Exception as e:
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