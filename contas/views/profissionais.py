from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import timedelta

from ..models import PerfilProfissional, Especialidade
from ..calendar_utils import gerar_blocos_disponiveis_para_paciente


def lista_profissionais(request):
    """View para a lista de profissionais"""
    query = request.GET.get('q')
    selected_specialty_ids = request.GET.getlist('especialidade')

    # Começa com todos os perfis
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
            valid_specialty_ids = []

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

    # Paginação
    paginator = Paginator(profissionais_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    todas_especialidades = Especialidade.objects.all()  # type: ignore

    contexto = {
        'page_obj': page_obj,
        'todas_especialidades': todas_especialidades,
        'search_query': query,
        'selected_specialty_ids': valid_specialty_ids,
    }
    return render(request, 'contas/lista_profissionais.html', contexto)


def perfil_profissional_detail(request, pk):
    """View para detalhes do perfil profissional"""
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