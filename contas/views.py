# contas/views.py

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
from datetime import time, timedelta, date, datetime # Importa timedelta e date
import requests # Para fazer chamadas HTTP à API do Daily.co


from .calendar_utils import gerar_eventos_completos_para_calendario_profissional, gerar_slots_disponiveis_para_paciente

from .models import (
    PerfilProfissional, PerfilPaciente, Especialidade, Agendamento,
    RegraDisponibilidade # <-- CORRIGIDO
    # Certifique-se que Disponibilidade e DisponibilidadeAvulsa foram removidos desta lista
)

from .forms import (
    RegistroUsuarioForm, PerfilProfissionalForm, PerfilPacienteForm,
    CustomAuthenticationForm, RegraDisponibilidadeForm
    # Assegure-se de que DisponibilidadeForm e DisponibilidadeAvulsaForm foram removidos
    # Poderíamos adicionar RegraDisponibilidadeForm aqui depois, quando ele for criado.
)

# CLASSES CBV

class GerenciarRegrasDisponibilidadeView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = RegraDisponibilidade
    template_name = 'contas/gerenciar_regras_disponibilidade.html'
    context_object_name = 'regras_disponibilidade'

    def test_func(self):
        return hasattr(self.request.user, 'perfil_profissional')

    def handle_no_permission(self):
        messages.error(self.request, "Esta página é acessível apenas para profissionais.")
        return redirect('contas:index')

    def get_queryset(self):
        return RegraDisponibilidade.objects.filter(
            profissional=self.request.user.perfil_profissional
        ).order_by('tipo_regra', 'dia_semana', 'data_hora_inicio_especifica', 'hora_inicio_recorrente')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = RegraDisponibilidadeForm()
        return context

    def post(self, request, *args, **kwargs):
        form = RegraDisponibilidadeForm(request.POST)
        perfil_profissional = request.user.perfil_profissional

        if form.is_valid():
            try:
                nova_regra = form.save(commit=False)
                nova_regra.profissional = perfil_profissional
                nova_regra.save()
                messages.success(request, "Nova regra de disponibilidade adicionada com sucesso!")
                return redirect(reverse_lazy('contas:gerenciar_regras_disponibilidade'))
            except IntegrityError:
                messages.error(request, "Não foi possível salvar. Verifique se este horário já não existe ou há um conflito.")
            except ValidationError as e:
                messages.error(request, "Erro de validação ao salvar a regra.")
                for field, field_errors in e.message_dict.items():
                    for error_msg in field_errors:
                        if field == '__all__':
                            form.add_error(None, error_msg)
                        else:
                            form.add_error(field, error_msg)
            except Exception as e:
                messages.error(request, f"Ocorreu um erro inesperado: {e}")
        else:
            messages.error(request, "Por favor, corrija os erros no formulário abaixo.")

        self.object_list = self.get_queryset()
        context = self.get_context_data(form=form)
        return self.render_to_response(context)


class EditarRegraDisponibilidadeView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = RegraDisponibilidade
    form_class = RegraDisponibilidadeForm
    template_name = 'contas/editar_regra_disponibilidade.html'
    pk_url_kwarg = 'regra_id'
    context_object_name = 'regra'
    success_url = reverse_lazy('contas:gerenciar_regras_disponibilidade')

    def test_func(self):
        if not hasattr(self.request.user, 'perfil_profissional'):
            return False
        regra = self.get_object()
        return regra.profissional == self.request.user.perfil_profissional

    def handle_no_permission(self):
        if not hasattr(self.request.user, 'perfil_profissional'):
            messages.error(self.request, "Ação não permitida. Apenas profissionais podem editar regras.")
            return redirect('contas:index')
        else:
            messages.error(self.request, "Você não tem permissão para editar esta regra de disponibilidade.")
            return redirect('contas:gerenciar_regras_disponibilidade')

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            messages.success(self.request, "Regra de disponibilidade atualizada com sucesso!")
            return response
        except IntegrityError:
            form.add_error(None, "A alteração cria um conflito com um horário já existente ou outra restrição.")
            messages.error(self.request, "Erro de integridade ao salvar. Verifique os dados.")
            return self.form_invalid(form)
        # ValidationError deveria ser pega pelo form.is_valid() e adicionada a form.errors
        # Mas se precisarmos pegar explicitamente após o save (incomum para model.clean())
        except ValidationError as e: # Captura ValidationError do modelo, se não pego antes
            messages.error(self.request, "Erro de validação ao salvar a regra (form_valid).")
            for field, field_errors in e.message_dict.items():
                for error_msg in field_errors:
                    if field == '__all__':
                        form.add_error(None, error_msg)
                    else:
                        form.add_error(field, error_msg)
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Ocorreu um erro inesperado ao salvar: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        # Apenas adiciona mensagem genérica se o form não tiver erros específicos já (raro aqui)
        # As mensagens de erro do IntegrityError/ValidationError já foram adicionadas ao form em form_valid
        # e o super().form_invalid(form) vai re-renderizar o template com esses erros.
        # Esta mensagem é um fallback.
        has_form_errors = any(form.non_field_errors() or any(field_errors for field_errors in form.errors.values()))
        if not has_form_errors:
             messages.error(self.request, "Por favor, corrija os erros no formulário.")
        return super().form_invalid(form)


class ExcluirRegraDisponibilidadeView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = RegraDisponibilidade
    pk_url_kwarg = 'regra_id'
    success_url = reverse_lazy('contas:gerenciar_regras_disponibilidade')
    template_name = 'contas/regradisponibilidade_confirm_delete.html'

    def test_func(self):
        if not hasattr(self.request.user, 'perfil_profissional'):
            return False
        regra = self.get_object()
        return regra.profissional == self.request.user.perfil_profissional

    def handle_no_permission(self):
        if not hasattr(self.request.user, 'perfil_profissional'):
            messages.error(self.request, "Ação não permitida.")
            return redirect('contas:index')
        else:
            messages.error(self.request, "Você não tem permissão para excluir esta regra de disponibilidade.")
            return redirect('contas:gerenciar_regras_disponibilidade')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        detalhes_regra = str(self.object)
        # Chama o método delete da classe pai (que efetivamente deleta o objeto)
        # e lida com o redirecionamento para success_url.
        # Envolver em try-except para o caso raro de falha na deleção.
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(self.request, f"Regra de disponibilidade ({detalhes_regra}) excluída com sucesso.")
            return response
        except Exception as e:
            messages.error(self.request, f"Ocorreu um erro ao excluir a regra de disponibilidade: {e}")
            return redirect(self.success_url) # Ou alguma página de erro


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


# View para exibir o perfil detalhado de um profissional (PARA PACIENTES AGENDAR)
# Atualizada para agrupar slots em blocos maiores e passar horários individuais para o modal
def perfil_profissional_detail(request, pk):
    perfil = get_object_or_404(PerfilProfissional, pk=pk)
    # print(f"\n--- [DEBUG PERFIL DETAIL] Iniciando para Profissional PK: {pk} ---")

    hoje = timezone.localdate()
    dias_a_mostrar = 7 
    data_fim_periodo_calendario = hoje + timedelta(days=dias_a_mostrar)
    
    duracao_consulta_timedelta = timedelta(hours=1) 
    incremento_geracao_slot_timedelta = timedelta(minutes=30) 

    tz_padrao = timezone.get_default_timezone()
    agora = timezone.now()
    fim_busca_geral_agendamentos = timezone.make_aware(datetime.combine(data_fim_periodo_calendario, time.max), tz_padrao)

    regras_disponibilidade_prof = perfil.regras_disponibilidade.all()
    agendamentos_existentes_objs = Agendamento.objects.filter(
        profissional=perfil,
        data_hora__gte=agora, 
        data_hora__lt=fim_busca_geral_agendamentos,
        status__in=['PENDENTE', 'CONFIRMADO']
    )
    
    # Criar uma lista de intervalos de tempo já agendados
    booked_intervals = []
    for ag in agendamentos_existentes_objs:
        booked_intervals.append((ag.data_hora, ag.data_hora + duracao_consulta_timedelta))

    # --- Gerar TODOS os Slots Potenciais com base em RegraDisponibilidade ---
    all_potential_slots_set = set()

    for i in range(dias_a_mostrar):
        dia_atual_iter = hoje + timedelta(days=i)
        dia_semana_atual_iter = dia_atual_iter.weekday()

        for regra in regras_disponibilidade_prof:
            if regra.tipo_regra == 'SEMANAL' and regra.dia_semana == dia_semana_atual_iter:
                if regra.hora_inicio_recorrente and regra.hora_fim_recorrente:
                    bloco_inicio_dt = timezone.make_aware(datetime.combine(dia_atual_iter, regra.hora_inicio_recorrente), tz_padrao)
                    bloco_fim_dt = timezone.make_aware(datetime.combine(dia_atual_iter, regra.hora_fim_recorrente), tz_padrao)
                    hora_inicio_slot_potencial = bloco_inicio_dt
                    while hora_inicio_slot_potencial < bloco_fim_dt:
                        if hora_inicio_slot_potencial + duracao_consulta_timedelta <= bloco_fim_dt:
                            all_potential_slots_set.add(hora_inicio_slot_potencial)
                        hora_inicio_slot_potencial += incremento_geracao_slot_timedelta
            
            elif regra.tipo_regra == 'ESPECIFICA':
                if regra.data_hora_inicio_especifica and regra.data_hora_fim_especifica:
                    bloco_inicio_dt_especifico = regra.data_hora_inicio_especifica.astimezone(tz_padrao)
                    bloco_fim_dt_especifico = regra.data_hora_fim_especifica.astimezone(tz_padrao)
                    if bloco_inicio_dt_especifico.date() <= dia_atual_iter <= bloco_fim_dt_especifico.date():
                        hora_inicio_slot_potencial = timezone.make_aware(datetime.combine(dia_atual_iter, time.min), tz_padrao)
                        if bloco_inicio_dt_especifico > hora_inicio_slot_potencial:
                            hora_inicio_slot_potencial = bloco_inicio_dt_especifico
                        limite_fim_dia_atual = timezone.make_aware(datetime.combine(dia_atual_iter + timedelta(days=1), time.min), tz_padrao)
                        fim_real_bloco_no_dia = min(bloco_fim_dt_especifico, limite_fim_dia_atual)
                        while hora_inicio_slot_potencial < fim_real_bloco_no_dia:
                            if hora_inicio_slot_potencial + duracao_consulta_timedelta <= fim_real_bloco_no_dia:
                                all_potential_slots_set.add(hora_inicio_slot_potencial)
                            hora_inicio_slot_potencial += incremento_geracao_slot_timedelta
    
    # --- Filtrar Slots Potenciais (remove passados e os que colidem com agendamentos) ---
    slots_validos_final = []
    for slot_inicio_potencial in sorted(list(all_potential_slots_set)):
        if slot_inicio_potencial <= agora: 
            continue
        
        slot_fim_potencial = slot_inicio_potencial + duracao_consulta_timedelta
        slot_ocupado_por_agendamento = False
        for booked_start, booked_end in booked_intervals:
            if (slot_inicio_potencial < booked_end) and (slot_fim_potencial > booked_start):
                slot_ocupado_por_agendamento = True
                break 
        
        if slot_ocupado_por_agendamento:
            continue
            
        slots_validos_final.append(slot_inicio_potencial)
    
    # print(f"[DEBUG PERFIL DETAIL] Slots VÁLIDOS INDIVIDUAIS ({len(slots_validos_final)}): {[s.isoformat() for s in slots_validos_final]}")

    # --- Agrupar slots individuais contíguos em blocos visuais maiores ---
    blocos_visuais_para_paciente = []
    if slots_validos_final: # A lista já está ordenada
        bloco_atual_start_dt = slots_validos_final[0]
        bloco_atual_end_dt_visual = slots_validos_final[0] + duracao_consulta_timedelta
        horarios_iniciais_no_bloco_atual_iso = [slots_validos_final[0].isoformat()]

        for i in range(1, len(slots_validos_final)):
            slot_atual_inicio_dt = slots_validos_final[i]
            
            # Verifica se o slot atual é contíguo ao *último slot individual adicionado ao bloco atual*
            # E se ele ainda estaria dentro do "alcance" visual do primeiro slot do bloco se fosse um único evento.
            # A segunda condição (slot_atual_inicio_dt < bloco_atual_end_dt_visual) era para uma lógica diferente.
            # O correto é verificar se o slot atual começa onde o anterior terminou (considerando o incremento)
            # OU se começa exatamente onde o bloco visual atual terminaria.
            
            ultimo_slot_no_bloco_iso = horarios_iniciais_no_bloco_atual_iso[-1]
            ultimo_slot_no_bloco_dt = datetime.fromisoformat(ultimo_slot_no_bloco_iso)

            # Se o slot atual é o próximo slot esperado pelo incremento E o bloco visual pode ser estendido
            if slot_atual_inicio_dt == (ultimo_slot_no_bloco_dt + incremento_geracao_slot_timedelta) and \
               slot_atual_inicio_dt < (bloco_atual_start_dt + timedelta(hours=4)): # Limita o tamanho de um bloco visual para evitar blocos muito longos
                
                horarios_iniciais_no_bloco_atual_iso.append(slot_atual_inicio_dt.isoformat())
                bloco_atual_end_dt_visual = slot_atual_inicio_dt + duracao_consulta_timedelta # Atualiza o fim do bloco visual
            else: # Quebra de continuidade ou limite de tamanho do bloco visual
                blocos_visuais_para_paciente.append({
                    'title': 'Horários Disponíveis', 
                    'start': bloco_atual_start_dt.isoformat(),
                    'end': bloco_atual_end_dt_visual.isoformat(),
                    'extendedProps': {
                        'tipo': 'bloco_disponivel_paciente',
                        'horarios_iniciais_disponiveis_iso': list(horarios_iniciais_no_bloco_atual_iso)
                    }, 
                    'color': '#28a745', 'borderColor': '#23923d'
                })
                # Inicia um novo bloco
                bloco_atual_start_dt = slot_atual_inicio_dt
                bloco_atual_end_dt_visual = slot_atual_inicio_dt + duracao_consulta_timedelta
                horarios_iniciais_no_bloco_atual_iso = [slot_atual_inicio_dt.isoformat()]
        
        # Adiciona o último bloco que estava sendo construído
        if bloco_atual_start_dt: # Garante que há um bloco para adicionar
            blocos_visuais_para_paciente.append({
                'title': 'Horários Disponíveis', 
                'start': bloco_atual_start_dt.isoformat(),
                'end': bloco_atual_end_dt_visual.isoformat(),
                'extendedProps': {
                    'tipo': 'bloco_disponivel_paciente',
                    'horarios_iniciais_disponiveis_iso': horarios_iniciais_no_bloco_atual_iso
                }, 
                'color': '#28a745', 'borderColor': '#23923d'
            })
    
    # print(f"[DEBUG PERFIL DETAIL] BLOCOS VISUAIS PARA PACIENTE ({len(blocos_visuais_para_paciente)}): {blocos_visuais_para_paciente}")
    calendar_events = blocos_visuais_para_paciente

    contexto = {
        'perfil': perfil,
        'calendar_events_data': calendar_events,
        'duracao_consulta_minutos': int(duracao_consulta_timedelta.total_seconds() // 60),
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
    agendamentos_passados = None
    is_profissional = False # Flag para ajudar o template

    now = timezone.now() # Pega a data e hora atual com fuso horário

    try:
        if hasattr(user, 'perfil_paciente'):
            # Se for paciente, busca agendamentos onde ele é o paciente
            perfil = user.perfil_paciente
            agendamentos = Agendamento.objects.filter(paciente=perfil)
            agendamentos_futuros = agendamentos.filter(data_hora__gte=now).order_by('data_hora')
            agendamentos_passados = agendamentos.filter(data_hora__lt=now).order_by('-data_hora') # Mais recentes primeiro
        elif hasattr(user, 'perfil_profissional'):
            # Se for profissional, busca agendamentos onde ele é o profissional
            perfil = user.perfil_profissional
            is_profissional = True # Define a flag
            agendamentos = Agendamento.objects.filter(profissional=perfil)
            agendamentos_futuros = agendamentos.filter(data_hora__gte=now).order_by('data_hora')
            agendamentos_passados = agendamentos.filter(data_hora__lt=now).order_by('-data_hora') # Mais recentes primeiro
        else:
            messages.warning(request, "Perfil não encontrado para listar agendamentos.")

    except Exception as e: # Captura genérica para debug, idealmente seria mais específico
         messages.error(request, f"Ocorreu um erro ao buscar seus agendamentos: {e}")


    contexto = {
        'agendamentos_futuros': agendamentos_futuros,
        'agendamentos_passados': agendamentos_passados,
        'is_profissional': is_profissional, # Passa a flag para o template
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

# View para criar um agendamento (requer POST e login)
@login_required
@require_POST # Garante que só aceite POST
def criar_agendamento(request, profissional_id, timestamp_str):
    user = request.user
    # Verifica se o usuário logado é um paciente
    if not hasattr(user, 'perfil_paciente'):
        messages.error(request, "Apenas pacientes podem agendar consultas.")
        return redirect('contas:lista_profissionais')

    perfil_paciente = user.perfil_paciente
    profissional = get_object_or_404(PerfilProfissional, pk=profissional_id)

    # Converte a string do timestamp de volta para um datetime aware
    try:
        slot_datetime = datetime.fromisoformat(timestamp_str)
        # Garante que está no timezone padrão do projeto se não tiver offset explícito (Z)
        # e normaliza para o timezone padrão (importante para comparação com BD)
        if slot_datetime.tzinfo is None or slot_datetime.tzinfo.utcoffset(slot_datetime) is None:
            slot_datetime = timezone.make_aware(slot_datetime, timezone.get_default_timezone())
        else:
            slot_datetime = slot_datetime.astimezone(timezone.get_default_timezone())

    except ValueError:
        messages.error(request, "Horário inválido selecionado.")
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)

    # --- Revalidação Crítica: Verifica se o slot AINDA está vago ---
    ja_existe = Agendamento.objects.filter(
        profissional=profissional,
        data_hora=slot_datetime,
        status__in=['PENDENTE', 'CONFIRMADO']
    ).exists()

    if ja_existe:
        messages.error(request, "Desculpe, este horário foi agendado por outra pessoa enquanto você visualizava. Por favor, escolha outro.")
        return redirect('contas:perfil_profissional_detail', pk=profissional_id)

    # --- Verifica se o slot é no futuro ---
    if slot_datetime <= timezone.now():
         messages.error(request, "Não é possível agendar horários no passado.")
         return redirect('contas:perfil_profissional_detail', pk=profissional_id)

    # --- Cria o Agendamento ---
    try:
        novo_agendamento = Agendamento.objects.create(
            paciente=perfil_paciente,
            profissional=profissional,
            data_hora=slot_datetime,
            status='PENDENTE' # Começa como pendente por padrão
        )
        messages.success(request, f"Agendamento solicitado com sucesso para {slot_datetime.strftime('%d/%m/%Y às %H:%M')}!")

        # ---- ENVIAR EMAIL PARA O PROFISSIONAL ----
        try:
            assunto = f"Nova Solicitação de Agendamento: {novo_agendamento.paciente.user.get_full_name() or novo_agendamento.paciente.user.username}"
            contexto_email = {
                'profissional_nome': novo_agendamento.profissional.user.get_full_name() or novo_agendamento.profissional.user.username,
                'paciente_nome': novo_agendamento.paciente.user.get_full_name() or novo_agendamento.paciente.user.username,
                'data_hora_agendamento': novo_agendamento.data_hora,
                'link_meus_agendamentos': request.build_absolute_uri(reverse('contas:meus_agendamentos')),
            }
            corpo_email_txt = render_to_string('contas/email/novo_agendamento_profissional.txt', contexto_email)
            # corpo_email_html = render_to_string('contas/email/novo_agendamento_profissional.html', contexto_email) # Para email HTML

            send_mail(
                assunto,
                corpo_email_txt,
                settings.DEFAULT_FROM_EMAIL,
                [novo_agendamento.profissional.user.email],
                # html_message=corpo_email_html, # Descomente para enviar versão HTML
                fail_silently=False, # Durante desenvolvimento, é bom ver erros
            )
            # messages.info(request, "Email de notificação enviado ao profissional.") # Opcional
        except Exception as e_mail:
            # Não quebra o fluxo principal se o email falhar, mas avisa no console do servidor
            print(f"ERRO AO ENVIAR EMAIL de novo agendamento para profissional: {e_mail}")
            messages.warning(request, "Agendamento criado, mas houve um problema ao notificar o profissional por email.")
        # ---- FIM DO ENVIO DE EMAIL ----

        return redirect('contas:meus_agendamentos')

    except Exception as e: # Captura outras exceções durante a criação do agendamento
        messages.error(request, f"Ocorreu um erro inesperado ao tentar agendar: {e}")
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
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        messages.error(request, "Apenas profissionais podem acessar esta página.")
        return redirect('contas:index')

    perfil = user.perfil_profissional
    tz_padrao = timezone.get_default_timezone()
    agora = timezone.now()
    hoje = timezone.localdate() # Necessário para o startRecur e lógica de período

    # Período de visualização para o calendário do profissional
    # Buscamos um pouco do passado para contexto de agendamentos e um período razoável no futuro
    data_inicio_periodo_geral = agora - timedelta(days=30) 
    data_fim_periodo_geral = agora + timedelta(days=90)  

    # --- Busca de Dados Relevantes ---
    # Busca TODAS as regras de disponibilidade (semanais e específicas)
    todas_as_regras_disponibilidade = perfil.regras_disponibilidade.all().order_by('data_hora_inicio_especifica', 'hora_inicio_recorrente')
    
    # Agendamentos (todos os status para visualização do profissional)
    agendamentos_objs = perfil.agendamentos.filter(
        data_hora__gte=data_inicio_periodo_geral, data_hora__lt=data_fim_periodo_geral
    )
    
    # --- Processamento para Eventos FullCalendar ---
    all_events = [] # Lista Python de dicionários
    duracao_consulta_padrao = timedelta(hours=1) # Duração padrão para agendamentos
    
    # Cores alinhadas com a Identidade Visual "Hope Saúde"
    cor_disponivel_bloco = '#5cb85c' # Verde "calmo" para disponibilidade (ajuste se tiver um no manual)
                                     # O manual sugere Verde Sálvia (#B2C2B3) para detalhes/fundos.
                                     # Para blocos de disponibilidade, um verde mais claro mas sólido pode ser bom.
                                     # Se usar --hope-verde-salvia (#B2C2B3), o texto precisará ser escuro.
    borda_cor_disponivel_bloco = '#4cae4c' # Tom ligeiramente mais escuro para borda
    texto_cor_disponivel = '#FFFFFF' # Texto branco para contraste com o verde acima

    # cor_bloqueio_fundo = '#e9ecef' # Removido - Não há mais BloqueioTempo

    # 1. & 2. Processar Regras de Disponibilidade (Semanal e Específica)
    for regra in todas_as_regras_disponibilidade:
        if regra.tipo_regra == 'SEMANAL':
            if regra.dia_semana is not None and regra.hora_inicio_recorrente and regra.hora_fim_recorrente:
                fc_day = (regra.dia_semana + 1) % 7 # Converte dia Python (Mon=0) para FullCalendar (Sun=0)
                all_events.append({
                    'title': 'Disponível', 
                    'groupId': f'regra_disp_semanal_{regra.id}', # Para identificar o grupo de recorrência
                    'daysOfWeek': [ fc_day ], 
                    'startTime': regra.hora_inicio_recorrente.strftime('%H:%M:%S'),
                    'endTime': regra.hora_fim_recorrente.strftime('%H:%M:%S'), 
                    'display': 'block', # Para ser um bloco visível e mais proeminente
                    'color': cor_disponivel_bloco, 
                    'borderColor': borda_cor_disponivel_bloco,
                    'textColor': texto_cor_disponivel,
                    'extendedProps': {'tipo': 'disponibilidade_semanal', 'id_original': regra.id}
                    # 'startRecur': hoje.isoformat(), # Para iniciar a recorrência a partir de hoje
                })
        elif regra.tipo_regra == 'ESPECIFICA':
            if regra.data_hora_inicio_especifica and regra.data_hora_fim_especifica:
                start_dt = regra.data_hora_inicio_especifica.astimezone(tz_padrao)
                end_dt = regra.data_hora_fim_especifica.astimezone(tz_padrao)
                
                # Adiciona apenas se o período específico interceptar o período geral de visualização
                if start_dt < data_fim_periodo_geral and end_dt > data_inicio_periodo_geral:
                    all_events.append({
                        'title': 'Disponível', 
                        'start': start_dt.isoformat(),
                        'end': end_dt.isoformat(), # Mostra o bloco específico com sua duração total
                        'color': cor_disponivel_bloco, 
                        'borderColor': borda_cor_disponivel_bloco,
                        'textColor': texto_cor_disponivel,
                        'id': f'regra_disp_esp_{regra.id}',
                        'extendedProps': {'tipo': 'regra_disponibilidade_especifica', 'id_original': regra.id}
                    })

    # Lógica de AGRUPAR Regras de Disponibilidade Específicas Contíguas (VISUALMENTE)
    # Esta lógica é para a VIEW do profissional, para que ele veja blocos contínuos.
    # A view do PACIENTE (perfil_profissional_detail) quebra em slots agendáveis.
    # (Mantida da Resposta #151, com o título ajustado)
    
    # Primeiro, separe os eventos de disponibilidade específica dos outros para o agrupamento
    eventos_disp_especifica_para_agrupar = [e for e in all_events if e.get('extendedProps', {}).get('tipo') == 'disponibilidade_especifica']
    outros_eventos = [e for e in all_events if e.get('extendedProps', {}).get('tipo') != 'disponibilidade_especifica']
    
    all_events_final_agrupado = list(outros_eventos) # Começa com os que não são para agrupar

    if eventos_disp_especifica_para_agrupar:
        # Ordena por data de início para garantir o agrupamento correto
        eventos_disp_especifica_para_agrupar.sort(key=lambda x: x['start'])
        
        merged_specific_slots = []
        current_merged_event = None

        for evento_esp in eventos_disp_especifica_para_agrupar:
            start_dt_obj = datetime.fromisoformat(evento_esp['start'])
            end_dt_obj = datetime.fromisoformat(evento_esp['end'])

            if current_merged_event is None:
                current_merged_event = {
                    'title': 'Disponível', # Título para o bloco agrupado
                    'start_obj': start_dt_obj, # Guardar como objeto datetime para comparação
                    'end_obj': end_dt_obj,
                    'ids_originais': evento_esp['extendedProps']['id_original'], # Pode ser uma lista se já agrupado, ou um int
                    'color': evento_esp['color'], # Mantém a cor
                    'borderColor': evento_esp['borderColor'],
                    'textColor': evento_esp['textColor']
                }
                # Garante que ids_originais seja sempre uma lista
                if not isinstance(current_merged_event['ids_originais'], list):
                    current_merged_event['ids_originais'] = [current_merged_event['ids_originais']]

            elif start_dt_obj == current_merged_event['end_obj']: # Contíguo
                current_merged_event['end_obj'] = end_dt_obj # Estende o fim
                # Adiciona o ID da regra original se não for uma lista já (caso de evento não agrupado anteriormente)
                if isinstance(evento_esp['extendedProps']['id_original'], list):
                    current_merged_event['ids_originais'].extend(evento_esp['extendedProps']['id_original'])
                else:
                    current_merged_event['ids_originais'].append(evento_esp['extendedProps']['id_original'])
                # Remove duplicatas de IDs se houver (improvável, mas seguro)
                current_merged_event['ids_originais'] = sorted(list(set(current_merged_event['ids_originais'])))
            else: # Quebra de continuidade
                if current_merged_event:
                    all_events_final_agrupado.append({
                        'title': current_merged_event['title'],
                        'start': current_merged_event['start_obj'].isoformat(),
                        'end': current_merged_event['end_obj'].isoformat(),
                        'color': current_merged_event['color'],
                        'borderColor': current_merged_event['borderColor'],
                        'textColor': current_merged_event['textColor'],
                        'id': f'regra_disp_esp_agrupada_{"_".join(map(str, current_merged_event["ids_originais"]))}',
                        'extendedProps': {'tipo': 'disponibilidade_especifica_agrupada', 'ids_originais': current_merged_event['ids_originais']}
                    })
                current_merged_event = {
                    'title': 'Disponível', 'start_obj': start_dt_obj, 'end_obj': end_dt_obj,
                    'ids_originais': [evento_esp['extendedProps']['id_original']] if not isinstance(evento_esp['extendedProps']['id_original'], list) else evento_esp['extendedProps']['id_original'],
                    'color': evento_esp['color'], 'borderColor': evento_esp['borderColor'], 'textColor': evento_esp['textColor']
                }
        
        if current_merged_event: # Adiciona o último bloco agrupado
            all_events_final_agrupado.append({
                'title': current_merged_event['title'],
                'start': current_merged_event['start_obj'].isoformat(),
                'end': current_merged_event['end_obj'].isoformat(),
                'color': current_merged_event['color'],
                'borderColor': current_merged_event['borderColor'],
                'textColor': current_merged_event['textColor'],
                'id': f'regra_disp_esp_agrupada_{"_".join(map(str, current_merged_event["ids_originais"]))}',
                'extendedProps': {'tipo': 'disponibilidade_especifica_agrupada', 'ids_originais': current_merged_event['ids_originais']}
            })
    else: # Se não houver eventos específicos para agrupar, apenas usa os outros (semanais)
        all_events_final_agrupado = list(all_events) # all_events aqui conteria apenas os semanais


    # Adiciona os Agendamentos (eles sobreporão visualmente as disponibilidades)
    for ag in agendamentos_objs:
        paciente_full_name = ag.paciente.user.get_full_name()
        paciente_display_name = paciente_full_name or ag.paciente.user.username
        
        cor_agendamento = '#0d6efd'; borda_cor_agendamento = '#0a58ca'; texto_cor_agendamento = 'white'
        if ag.status == 'PENDENTE': cor_agendamento = '#ffc107'; borda_cor_agendamento = '#cc9a06'; texto_cor_agendamento = '#212529'
        elif ag.status == 'REALIZADO': cor_agendamento = '#198754'; borda_cor_agendamento = '#146c43'; texto_cor_agendamento = 'white'
        elif ag.status == 'CANCELADO': cor_agendamento = '#dc3545'; borda_cor_agendamento = '#b02a37'; texto_cor_agendamento = 'white'

        all_events_final_agrupado.append({
            'title': f"Consulta: {paciente_display_name} ({ag.get_status_display()})",
            'start': ag.data_hora.isoformat(), 
            'end': (ag.data_hora + duracao_consulta_padrao).isoformat(),
            'color': cor_agendamento, 
            'borderColor': borda_cor_agendamento,
            'textColor': texto_cor_agendamento,
            'id': f'ag_{ag.id}',
            'extendedProps': {'tipo': 'agendamento', 'id_original': ag.id, 'status': ag.status}
        })
    
    # --- Contexto Final ---
    contexto = {
        # Passa a LISTA PYTHON FINAL (com específicos agrupados) diretamente.
        'calendar_events_data': all_events_final_agrupado,
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

# @login_required
# def editar_regra_disponibilidade(request, regra_id):
#     user = request.user
#     # Verifica se o usuário é um profissional
#     if not hasattr(user, 'perfil_profissional'):
#         messages.error(request, "Ação não permitida.")
#         return redirect('contas:index')

#     # Busca a regra de disponibilidade específica ou retorna 404
#     regra = get_object_or_404(RegraDisponibilidade, pk=regra_id)

#     # Verifica se a regra pertence ao profissional logado
#     if regra.profissional != user.perfil_profissional:
#         messages.error(request, "Você não tem permissão para editar esta regra de disponibilidade.")
#         return redirect('contas:gerenciar_regras_disponibilidade')

#     if request.method == 'POST':
#         # Cria o formulário com os dados enviados E a instância existente para atualização
#         form = RegraDisponibilidadeForm(request.POST, instance=regra)
#         if form.is_valid():
#             try:
#                 form.save() # Salva as alterações na instância existente
#                 messages.success(request, "Regra de disponibilidade atualizada com sucesso!")
#                 return redirect('contas:gerenciar_regras_disponibilidade') # Volta para a lista
#             except IntegrityError:
#                 # Isso pode acontecer se a edição criar um conflito com unique_together (se definido)
#                 # Ou outra restrição de banco. O clean() do modelo já trata muita coisa.
#                 form.add_error(None, "A alteração cria um conflito com um horário já existente ou outra restrição.")
#                 messages.error(request, "Erro de integridade ao salvar. Verifique os dados.")
#             except ValidationError as e: # Captura ValidationError do clean() do modelo
#                 messages.error(request, "Erro de validação. Por favor, corrija os erros abaixo.")
#                 # Erros já devem estar no form.errors
#             except Exception as e:
#                 messages.error(request, f"Ocorreu um erro inesperado ao salvar: {e}")
#         else:
#             messages.error(request, "Por favor, corrija os erros no formulário.")
#     else: # GET request
#         # Cria o formulário pré-preenchido com os dados da instância existente
#         form = RegraDisponibilidadeForm(instance=regra)

#     contexto = {
#         'form': form,
#         'regra': regra # Para referência no template, se necessário (ex: no título)
#     }
#     return render(request, 'contas/editar_regra_disponibilidade.html', contexto)



@login_required
@require_POST
def api_criar_disp_avulsa(request):
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        return JsonResponse({'status': 'error', 'message': 'Apenas profissionais podem adicionar disponibilidade.'}, status=403)

    try:
        data = json.loads(request.body)
        # Nomes dos campos esperados do JavaScript/ModelForm
        inicio_str = data.get('data_hora_inicio_especifica')
        fim_str = data.get('data_hora_fim_especifica')

        if not inicio_str or not fim_str:
            return JsonResponse({'status': 'error', 'message': 'Datas de início e fim são obrigatórias.'}, status=400)

        # Converte strings ISO para datetimes aware
        data_hora_inicio = datetime.fromisoformat(inicio_str)
        data_hora_fim = datetime.fromisoformat(fim_str)
        
        # (Validações como no BloqueioTempoForm e no clean() do modelo RegraDisponibilidade)
        if data_hora_inicio >= data_hora_fim:
            return JsonResponse({'status': 'error', 'message': 'Horário de início deve ser anterior ao horário de fim.'}, status=400)
        
        if data_hora_inicio < timezone.now():
             return JsonResponse({'status': 'error', 'message': 'Não é possível adicionar disponibilidade avulsa no passado.'}, status=400)


        # Cria a RegraDisponibilidade
        regra = RegraDisponibilidade(
            profissional=user.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=data_hora_inicio,
            data_hora_fim_especifica=data_hora_fim
        )
        regra.full_clean() # Chama as validações do modelo
        regra.save()
        
        # É bom retornar o evento criado para o FullCalendar adicionar dinamicamente,
        # mas refetchEvents() é mais simples por enquanto.
        return JsonResponse({'status': 'success', 'message': 'Disponibilidade avulsa criada com sucesso!'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dados JSON inválidos.'}, status=400)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': '; '.join(e.messages)}, status=400) # Usa e.messages se for de full_clean
    except Exception as e:
        print(f"Erro ao criar disponibilidade avulsa via API: {e}") # Log do erro no servidor
        return JsonResponse({'status': 'error', 'message': 'Erro interno ao criar disponibilidade avulsa.'}, status=500)


# @login_required
# @require_POST
# def api_excluir_regra_disponibilidade(request, regra_id): # Pode ser a mesma 'excluir_regra_disponibilidade' adaptada
#     user = request.user
#     if not hasattr(user, 'perfil_profissional'):
#         return JsonResponse({'status': 'error', 'message': 'Ação não permitida.'}, status=403)

#     regra = get_object_or_404(RegraDisponibilidade, pk=regra_id)
#     if regra.profissional != user.perfil_profissional:
#         return JsonResponse({'status': 'error', 'message': 'Você não tem permissão.'}, status=403)

#     # IMPORTANTE: Permitir excluir apenas regras do tipo 'ESPECIFICA' por aqui
#     if regra.tipo_regra != 'ESPECIFICA':
#         return JsonResponse({'status': 'error', 'message': 'Apenas disponibilidades específicas/avulsas podem ser excluídas diretamente do calendário desta forma.'}, status=400)

#     try:
#         regra.delete()
#         return JsonResponse({'status': 'success', 'message': 'Disponibilidade avulsa excluída com sucesso!'})
#     except Exception as e:
#         return JsonResponse({'status': 'error', 'message': f'Erro ao excluir disponibilidade: {str(e)}'}, status=500)



@login_required
@require_POST # Esta view só aceitará requisições POST
def api_editar_regra_disponibilidade(request, regra_id):
    user = request.user
    # Verifica se o usuário logado é um profissional
    if not hasattr(user, 'perfil_profissional'):
        return JsonResponse({'status': 'error', 'message': 'Apenas profissionais podem editar disponibilidades.'}, status=403)

    # Busca a regra de disponibilidade específica ou retorna 404 (Não Encontrado)
    regra = get_object_or_404(RegraDisponibilidade, pk=regra_id)
    perfil_profissional_logado = user.perfil_profissional

    # Autorização: verifica se a regra pertence ao profissional logado
    if regra.profissional != perfil_profissional_logado:
        return JsonResponse({'status': 'error', 'message': 'Você não tem permissão para editar esta regra de disponibilidade.'}, status=403)

    # Validação de Tipo: Apenas regras do tipo 'ESPECIFICA' podem ser editadas por esta API
    if regra.tipo_regra != 'ESPECIFICA':
        return JsonResponse({'status': 'error', 'message': 'Apenas disponibilidades específicas/avulsas podem ser editadas por esta interface.'}, status=400)

    try:
        # Carrega os dados do corpo da requisição JSON
        data = json.loads(request.body.decode('utf-8'))
        inicio_str = data.get('data_hora_inicio_especifica')
        fim_str = data.get('data_hora_fim_especifica')

        if not inicio_str or not fim_str:
            return JsonResponse({'status': 'error', 'message': 'Datas de início e fim são obrigatórias.'}, status=400)

        # Converte as strings ISO (enviadas pelo JS, geralmente como UTC com 'Z') para objetos datetime aware
        try:
            # .replace('Z', '+00:00') é importante para compatibilidade com fromisoformat se o 'Z' não for direto
            data_hora_inicio = datetime.fromisoformat(inicio_str.replace('Z', '+00:00'))
            data_hora_fim = datetime.fromisoformat(fim_str.replace('Z', '+00:00'))
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Formato de data/hora inválido. Use o formato ISO (YYYY-MM-DDTHH:MM:SSZ).'}, status=400)
        
        # Assegura que os datetimes estejam no fuso horário padrão do projeto para consistência
        tz_padrao = timezone.get_default_timezone()
        data_hora_inicio = data_hora_inicio.astimezone(tz_padrao)
        data_hora_fim = data_hora_fim.astimezone(tz_padrao)

        # Atualiza os campos da instância da regra
        regra.data_hora_inicio_especifica = data_hora_inicio
        regra.data_hora_fim_especifica = data_hora_fim
        # Os outros campos (dia_semana, horas recorrentes) já devem ser None devido ao clean() do modelo
        # ao salvar uma regra ESPECIFICA.

        regra.full_clean() # Roda todas as validações do modelo, incluindo o método clean()
        regra.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Disponibilidade específica atualizada com sucesso!',
            # Opcional: retornar o evento atualizado se o JS for manipular isso em vez de refetchEvents()
            # 'event': {
            #     'id': f'regra_disp_esp_{regra.id}_slot_{regra.data_hora_inicio_especifica.astimezone(tz_padrao).strftime("%H%M")}',
            #     'title': 'Disponível',
            #     'start': regra.data_hora_inicio_especifica.isoformat(),
            #     'end': regra.data_hora_fim_especifica.isoformat(), # Se a regra é um bloco único
            #     'color': '#5cb85c',
            #     'borderColor': '#4cae4c',
            #     'extendedProps': {'tipo': 'regra_disponibilidade_especifica', 'id_original': regra.id}
            # }
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dados JSON inválidos na requisição.'}, status=400)
    except ValidationError as e:
        # Converte o dicionário de erros de validação em uma string mais amigável
        error_messages = []
        for field, errors in e.message_dict.items():
            for error in errors:
                error_messages.append(f"{RegraDisponibilidade._meta.get_field(field).verbose_name.capitalize() if field != '__all__' else 'Erro geral'}: {error}")
        return JsonResponse({'status': 'error', 'message': '; '.join(error_messages)}, status=400)
    except Exception as e:
        # Logar o erro real no servidor para debug
        print(f"Erro inesperado em api_editar_regra_disponibilidade: {type(e).__name__} - {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno ao tentar atualizar a disponibilidade.'}, status=500)

@login_required
@require_POST
def api_excluir_regras_disponibilidade_lista(request):
    user = request.user
    if not hasattr(user, 'perfil_profissional'):
        return JsonResponse({'status': 'error', 'message': 'Ação não permitida.'}, status=403)

    try:
        data = json.loads(request.body.decode('utf-8'))
        ids_para_excluir = data.get('ids')

        if not ids_para_excluir or not isinstance(ids_para_excluir, list) or not all(isinstance(id_val, int) for id_val in ids_para_excluir):
            return JsonResponse({'status': 'error', 'message': 'Lista de IDs inválida ou não fornecida.'}, status=400)

        # Busca apenas as regras que pertencem ao profissional e são do tipo ESPECIFICA
        regras_a_excluir = RegraDisponibilidade.objects.filter(
            pk__in=ids_para_excluir,
            profissional=user.perfil_profissional,
            tipo_regra='ESPECIFICA' # Segurança extra
        )

        count_excluidas = regras_a_excluir.count()

        if count_excluidas == 0 and len(ids_para_excluir) > 0 : # Tentou excluir algo, mas nada foi válido/encontrado
             return JsonResponse({'status': 'error', 'message': 'Nenhuma regra válida para exclusão foi encontrada ou você não tem permissão.'}, status=404)

        if count_excluidas > 0:
            regras_a_excluir.delete()

        return JsonResponse({'status': 'success', 'message': f'{count_excluidas} regra(s) de disponibilidade específica excluída(s) com sucesso.'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dados JSON inválidos.'}, status=400)
    except Exception as e:
        print(f"Erro em api_excluir_regras_disponibilidade_lista: {e}")
        return JsonResponse({'status': 'error', 'message': 'Erro interno ao excluir regras de disponibilidade.'}, status=500)


@login_required
def api_obter_ou_criar_sala_video(request, agendamento_id):
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id)
    user = request.user
    agora = timezone.now()

    # Autorização
    is_paciente_do_agendamento = hasattr(user, 'perfil_paciente') and agendamento.paciente == user.perfil_paciente
    is_profissional_do_agendamento = hasattr(user, 'perfil_profissional') and agendamento.profissional == user.perfil_profissional

    if not (is_paciente_do_agendamento or is_profissional_do_agendamento):
        return JsonResponse({'status': 'error', 'message': 'Você não tem permissão para acessar esta sala de vídeo.'}, status=403)

    # Validação de Status e Horário da Consulta
    if agendamento.status != 'CONFIRMADO':
        return JsonResponse({'status': 'error', 'message': 'Esta consulta não está confirmada e não pode ser iniciada.'}, status=400)
    
    horario_inicio_consulta = agendamento.data_hora
    duracao_consulta_timedelta = timedelta(hours=1) 
    horario_fim_consulta_estimado = horario_inicio_consulta + duracao_consulta_timedelta

    if agora < (horario_inicio_consulta - timedelta(minutes=30)): # Permite entrar 30 min antes
        return JsonResponse({'status': 'error', 'message': 'Ainda é muito cedo para entrar nesta consulta. Tente mais perto do horário agendado.'}, status=400)
    
    if agora > (horario_fim_consulta_estimado + timedelta(hours=1)): 
        return JsonResponse({'status': 'error', 'message': 'O tempo para esta consulta já expirou.'}, status=400)

    # --- Lógica para obter ou criar sala e token ---
    url_base_da_sala = agendamento.url_videochamada
    nome_da_sala_daily = None 
    # Se você salvou o nome da sala Daily.co no modelo Agendamento, use-o. Ex:
    # nome_da_sala_daily = agendamento.daily_co_room_name 

    # Se a URL da sala NÃO existe no nosso banco, CRIA a sala no Daily.co
    if not url_base_da_sala:
        try:
            if not settings.DAILY_CO_API_KEY:
                print("[API VÍDEO ERRO] Chave de API do Daily.co não configurada.")
                return JsonResponse({'status': 'error', 'message': 'Serviço de vídeo indisponível (config).'}, status=503)

            print(f"[API VÍDEO] Criando nova sala para agendamento {agendamento_id}...")
            headers_room = {
                'Authorization': f'Bearer {settings.DAILY_CO_API_KEY}',
                'Content-Type': 'application/json',
            }
            nbf_unix = int((horario_inicio_consulta - timedelta(minutes=30)).timestamp())
            exp_unix = int((horario_fim_consulta_estimado + timedelta(minutes=30)).timestamp())

            room_properties_payload = {
                'privacy': 'private',
                'properties': {
                    'start_audio_off': False, 'start_video_off': False,
                    'enable_chat': False, 'enable_screenshare': False,
                    'enable_people_ui': False, 'enable_prejoin_ui': True,
                    'nbf': nbf_unix, 'exp': exp_unix, 'max_participants': 2,
                    'eject_at_room_exp': True,
                }
            }
            
            daily_api_url_rooms = 'https://api.daily.co/v1/rooms'
            response_room = requests.post(daily_api_url_rooms, headers=headers_room, json=room_properties_payload)
            
            print(f"[API VÍDEO] Resposta Daily.co (Criar Sala) Status: {response_room.status_code}")
            response_room.raise_for_status()
            
            room_data = response_room.json()
            url_base_da_sala = room_data.get('url')
            nome_da_sala_daily = room_data.get('name') # GUARDA O NOME DA SALA

            if not url_base_da_sala or not nome_da_sala_daily:
                print(f"[API VÍDEO ERRO] URL ou nome da sala não retornados: {room_data}")
                raise Exception("Não foi possível obter URL ou nome da sala da API Daily.co.")

            agendamento.url_videochamada = url_base_da_sala
            # Se você adicionou um campo para o nome da sala no modelo Agendamento:
            # agendamento.nome_sala_daily = nome_da_sala_daily 
            agendamento.save()
            print(f"[API VÍDEO] Sala criada: {url_base_da_sala} (Nome: {nome_da_sala_daily})")

        except requests.exceptions.HTTPError as http_err:
            error_content = "N/A"; response_obj = http_err.response
            try: error_content = response_obj.json() 
            except: error_content = response_obj.text
            print(f"[API VÍDEO ERRO HTTP] Criar Sala: {http_err} - Detalhes: {error_content}")
            return JsonResponse({'status': 'error', 'message': f'Erro ({response_obj.status_code}) com serviço de vídeo ao criar sala.'}, status=500)
        except Exception as e:
            print(f"Erro ao CRIAR sala de vídeo para agendamento {agendamento_id}: {type(e).__name__} - {e}")
            return JsonResponse({'status': 'error', 'message': f'Erro ao configurar sala de vídeo: {str(e)}'}, status=500)
    
    # Se não pegamos o nome da sala na criação (porque já existia), tenta extrair da URL
    if not nome_da_sala_daily and url_base_da_sala:
        partes_url = url_base_da_sala.strip('/').split('/')
        nome_da_sala_daily = partes_url[-1] if partes_url else None

    if not nome_da_sala_daily:
        print(f"[API VÍDEO ERRO] Nome da sala não disponível para gerar token (Ag. ID: {agendamento_id}). URL base: {url_base_da_sala}")
        return JsonResponse({'status': 'error', 'message': 'Configuração da sala incompleta para gerar token de acesso.'}, status=500)

    # Agora, GERA UM TOKEN para o usuário atual para a sala 'nome_da_sala_daily'
    try:
        print(f"[API VÍDEO] Gerando token para sala '{nome_da_sala_daily}' para usuário '{user.username}'...")
        headers_token = {
            'Authorization': f'Bearer {settings.DAILY_CO_API_KEY}',
            'Content-Type': 'application/json',
        }
        # Token expira um pouco depois da consulta (ex: 1h15m após agora)
        token_exp_unix = int((timezone.now() + timedelta(hours=1, minutes=15)).timestamp()) 
        
        # --- PAYLOAD CORRIGIDO PARA O TOKEN ---
        token_properties_payload = {
            # 'room_name': nome_da_sala_daily, # Removido do payload principal, vai dentro de 'properties' se necessário
            'properties': {
                'room_name': nome_da_sala_daily,  # Nome da sala para a qual o token se aplica
                'user_name': user.username,       # Nome de exibição do usuário na chamada
                'is_owner': is_profissional_do_agendamento, # Se este token é para o "dono" da sala
                'exp': token_exp_unix,            # Timestamp de expiração do token
                'start_audio_off': True,          # Usuário entra com áudio desligado
                'start_video_off': True,          # Usuário entra com vídeo desligado
                # REMOVIDOS: 'enable_screenshare': False, 
                # REMOVIDOS: 'enable_chat': False,
                # Essas configurações geralmente são da sala. Se você quiser que o TOKEN
                # especificamente desabilite algo que a sala permite, a sintaxe pode ser diferente
                # ou via um objeto 'permissions'. Consulte a documentação do Daily.co.
                # Por enquanto, vamos omiti-los para evitar o erro "unknown parameter".
            }
            # Se 'room_name' não for dentro de 'properties', mas um parâmetro de topo para a API de token, ajuste.
            # Ex: (VERIFIQUE A DOC DO DAILY.CO)
            # 'room_name': nome_da_sala_daily,
            # 'user_id': str(user.id), # Um ID único para o usuário
            # 'user_name': user.username,
            # 'is_owner': is_profissional_do_agendamento,
            # 'exp': token_exp_unix
        }
        
        daily_api_url_tokens = 'https://api.daily.co/v1/meeting-tokens'
        print(f"[API VÍDEO] Enviando para Daily.co (Criar Token): {daily_api_url_tokens} com payload: {token_properties_payload}") # DEBUG
        response_token = requests.post(daily_api_url_tokens, headers=headers_token, json=token_properties_payload)

        print(f"[API VÍDEO] Resposta Daily.co (Criar Token) Status: {response_token.status_code}")
        # print(f"[API VÍDEO] Resposta Daily.co (Criar Token) Conteúdo: {response_token.text}") # Para debug detalhado
        response_token.raise_for_status()
        
        token_data = response_token.json()
        meeting_token = token_data.get('token')

        if not meeting_token:
            print(f"[API VÍDEO ERRO] Token não retornado pela API ao criar token: {token_data}")
            raise Exception("Token não retornado pela API Daily.co.")

        # Monta a URL final da sala COM o token
        room_url_final_com_token = f"{url_base_da_sala}?t={meeting_token}"
        print(f"[API VÍDEO] Token gerado. URL final para usuário: {room_url_final_com_token}")
        
        return JsonResponse({'status': 'success', 'room_url': room_url_final_com_token})

    except requests.exceptions.HTTPError as http_err:
        error_content = "N/A"; response_obj = http_err.response
        try: error_content = response_obj.json()
        except: error_content = response_obj.text
        print(f"[API VÍDEO ERRO HTTP] Gerar Token: {http_err} - Detalhes: {error_content}")
        msg_erro_api = "Erro com o serviço de vídeo ao tentar gerar acesso à sala."
        if isinstance(error_content, dict) and 'info' in error_content:
            msg_erro_api = error_content['info'] 
        
        return JsonResponse({'status': 'error', 'message': msg_erro_api}, status=500)
    except Exception as e:
        print(f"Erro ao GERAR TOKEN para agendamento {agendamento_id}: {type(e).__name__} - {e}")
        return JsonResponse({'status': 'error', 'message': f'Erro ao preparar acesso à sala de vídeo: {str(e)}'}, status=500)



