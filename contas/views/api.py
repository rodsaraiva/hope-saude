# contas/views/api.py

from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta, datetime
import json
from dateutil import parser
from django.http import JsonResponse
from ..calendar_utils import gerar_blocos_disponiveis_para_paciente
from ..models import PerfilProfissional

from ..models import RegraDisponibilidade, Agendamento, Avaliacao
from .utils import api_success_response, api_error_response, validate_agendamento_permission


@login_required
@require_POST
def api_criar_disp_avulsa(request):
    """API para criar disponibilidade avulsa"""
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

        novo_inicio = parser.parse(inicio_str)
        novo_fim = parser.parse(fim_str)

        if novo_inicio.tzinfo is None:
            novo_inicio = novo_inicio.replace(tzinfo=timezone.get_default_timezone())
        if novo_fim.tzinfo is None:
            novo_fim = novo_fim.replace(tzinfo=timezone.get_default_timezone())

        perfil_profissional = user.perfil_profissional

        # LÓGICA DE FUSÃO ATUALIZADA
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
    """API para editar regra de disponibilidade"""
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
    """API para excluir múltiplas regras de disponibilidade"""
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
    """API para obter ou criar sala de videochamada"""
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
        room_url_final_com_token = agendamento.obter_ou_criar_url_sala_com_token(
            user=user,
            is_owner=is_profissional_do_agendamento
        )
        return api_success_response(data={'room_url': room_url_final_com_token})
    except Exception as e:
        return api_error_response(message=str(e), status_code=500)


@login_required
@require_POST
def api_submeter_avaliacao(request):
    """API para submeter avaliação de agendamento"""
    # Permissão: apenas pacientes podem avaliar
    if not hasattr(request.user, 'perfil_paciente'):
        return api_error_response(message="Apenas pacientes podem enviar avaliações.", status_code=403)

    try:
        data = json.loads(request.body)
        agendamento_id = data.get('agendamento_id')
        nota = data.get('nota')
        comentario = data.get('comentario', '')

        if not all([agendamento_id, nota]):
            return api_error_response(message="Dados incompletos para submeter a avaliação.")

        # Validação: O agendamento deve existir e pertencer ao paciente logado
        agendamento = get_object_or_404(Agendamento, pk=agendamento_id, paciente=request.user.perfil_paciente)

        # Lógica de Negócio:
        # 1. Só pode avaliar agendamentos realizados
        if agendamento.status != 'REALIZADO':
            return api_error_response(message="Só é possível avaliar consultas que já foram realizadas.")
        
        # 2. Só pode avaliar uma vez
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
        
        # Roda as validações do modelo
        nova_avaliacao.full_clean()
        nova_avaliacao.save()
        
        return api_success_response(
            data={'message': 'Avaliação enviada com sucesso!'},
            status_code=201
        )

    except Exception as e:
        print(f"Erro inesperado em api_submeter_avaliacao: {e}")
        return api_error_response(message="Ocorreu um erro interno.", status_code=500)


@require_GET
def api_disponibilidade_profissional(request, profissional_id):
    """
    Retorna os horários disponíveis para agendamento de um profissional em formato JSON.
    """
    try:
        perfil = PerfilProfissional.objects.get(pk=profissional_id)  # type: ignore[attr-defined]
    except PerfilProfissional.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({'error': 'Profissional não encontrado.'}, status=404)

    duracao_consulta = timedelta(hours=1)
    calendar_events = gerar_blocos_disponiveis_para_paciente(
        perfil_profissional=perfil,
        dias_a_mostrar=14,  # aumentar o range para garantir que todas as disponibilidades apareçam
        duracao_consulta_timedelta=duracao_consulta
    )
    return JsonResponse(calendar_events, safe=False) 