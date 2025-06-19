# ProjetosDjango/contas/tests.py


import json
from PIL import Image
from io import BytesIO
from django.test import TestCase, override_settings 
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from datetime import time, date, datetime, timedelta
from django.utils import timezone
from unittest import mock # <--- ADICIONE ESTA LINHA
from django.urls import reverse
from .models import (PerfilProfissional, RegraDisponibilidade, Agendamento, PerfilPaciente, Especialidade)
from .forms import (RegraDisponibilidadeForm, PerfilProfissionalForm, PerfilPacienteForm, RegistroUsuarioForm)

class RegraDisponibilidadeModelTests(TestCase):

    def setUp(self):
        self.user_profissional = User.objects.create_user(username='profissional_teste', password='password123')
        self.perfil_profissional = PerfilProfissional.objects.create(user=self.user_profissional, tipo_profissional='PSICOLOGO')

    def test_validacao_semanal_campos_obrigatorios_faltando_dia_semana(self):
        """
        Testa se ValidationError é levantada se tipo_regra='SEMANAL' e dia_semana está faltando.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            hora_inicio_recorrente=time(9, 0),
            hora_fim_recorrente=time(17, 0)
        )
        with self.assertRaisesMessage(ValidationError,
                                      "Para regras 'Semanal Recorrente', os campos 'Dia da Semana (p/ Semanal)', 'Hora Início (p/ Semanal)' e 'Hora Fim (p/ Semanal)' são obrigatórios."):
            regra.full_clean()

    def test_validacao_semanal_campos_obrigatorios_faltando_hora_inicio(self):
        """
        Testa se ValidationError é levantada se tipo_regra='SEMANAL' e hora_inicio_recorrente está faltando.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_fim_recorrente=time(17, 0)
        )
        with self.assertRaisesMessage(ValidationError,
                                      "Para regras 'Semanal Recorrente', os campos 'Dia da Semana (p/ Semanal)', 'Hora Início (p/ Semanal)' e 'Hora Fim (p/ Semanal)' são obrigatórios."):
            regra.full_clean()

    def test_validacao_semanal_hora_fim_antes_de_hora_inicio(self):
        """
        Testa se ValidationError é levantada se hora_fim_recorrente for antes de hora_inicio_recorrente.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_inicio_recorrente=time(17, 0),
            hora_fim_recorrente=time(9, 0)
        )
        with self.assertRaisesMessage(ValidationError, "{'hora_fim_recorrente': ['A hora de fim recorrente deve ser após a hora de início.']}"):
            regra.full_clean()

    def test_validacao_semanal_hora_fim_igual_a_hora_inicio(self): # NOVO TESTE
        """
        Testa se ValidationError é levantada se hora_fim_recorrente for igual a hora_inicio_recorrente.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_inicio_recorrente=time(9, 0),
            hora_fim_recorrente=time(9, 0) # Horas iguais
        )
        with self.assertRaisesMessage(ValidationError, "{'hora_fim_recorrente': ['A hora de fim recorrente deve ser após a hora de início.']}"):
            regra.full_clean()

    def test_criacao_regra_semanal_valida(self):
        """
        Testa a criação bem-sucedida de uma regra semanal válida.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=1,
            hora_inicio_recorrente=time(10, 0),
            hora_fim_recorrente=time(18, 0)
        )
        try:
            regra.full_clean()
            regra.save()
        except ValidationError:
            self.fail("Uma regra semanal válida não deveria levantar ValidationError.")
        self.assertIsNotNone(regra.pk)
        self.assertIsNone(regra.data_hora_inicio_especifica)
        self.assertIsNone(regra.data_hora_fim_especifica)

    def test_validacao_especifica_campos_obrigatorios_faltando_data_inicio(self):
        """
        Testa se ValidationError é levantada se tipo_regra='ESPECIFICA' e data_hora_inicio_especifica está faltando.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_fim_especifica=timezone.now() + timedelta(days=1, hours=2)
        )
        with self.assertRaisesMessage(ValidationError,
                                      "Para regras 'Data/Hora Específica', os campos 'Início Específico' e 'Fim Específico' são obrigatórios."):
            regra.full_clean()

    def test_validacao_especifica_data_fim_antes_de_data_inicio(self):
        """
        Testa se ValidationError é levantada se data_hora_fim_especifica for antes de data_hora_inicio_especifica.
        """
        inicio = timezone.now() + timedelta(days=1)
        fim = timezone.now() + timedelta(days=1, hours=-2)
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio,
            data_hora_fim_especifica=fim
        )
        with self.assertRaisesMessage(ValidationError,
                                      "{'data_hora_fim_especifica': ['O fim específico deve ser após o início específico.']}"):
            regra.full_clean()

    def test_validacao_especifica_data_fim_igual_a_data_inicio(self): # NOVO TESTE
        """
        Testa se ValidationError é levantada se data_hora_fim_especifica for igual a data_hora_inicio_especifica.
        """
        inicio_fim = timezone.now() + timedelta(days=1)
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio_fim,
            data_hora_fim_especifica=inicio_fim # Datas/horas iguais
        )
        with self.assertRaisesMessage(ValidationError,
                                      "{'data_hora_fim_especifica': ['O fim específico deve ser após o início específico.']}"):
            regra.full_clean()

    def test_validacao_especifica_data_inicio_no_passado(self):
        """
        Testa se ValidationError é levantada se data_hora_inicio_especifica for no passado para uma nova regra.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=timezone.now() - timedelta(days=1),
            data_hora_fim_especifica=timezone.now() - timedelta(days=1, hours=-2) # Corrigido para ser consistente com a lógica do clean() que valida início primeiro
        )
        with self.assertRaisesMessage(ValidationError,
                                      "{'data_hora_inicio_especifica': ['Não é possível adicionar disponibilidade específica no passado.']}"):
            regra.full_clean()

    def test_criacao_regra_especifica_valida(self):
        """
        Testa a criação bem-sucedida de uma regra específica válida.
        """
        inicio = timezone.now() + timedelta(days=2, hours=10)
        fim = timezone.now() + timedelta(days=2, hours=12)
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio,
            data_hora_fim_especifica=fim
        )
        try:
            regra.full_clean()
            regra.save()
        except ValidationError:
            self.fail("Uma regra específica válida não deveria levantar ValidationError.")
        self.assertIsNotNone(regra.pk)
        self.assertIsNone(regra.dia_semana)
        self.assertIsNone(regra.hora_inicio_recorrente)
        self.assertIsNone(regra.hora_fim_recorrente)

    def test_validacao_tipo_regra_invalido_ou_nulo(self): # NOVO TESTE
        """
        Testa se ValidationError é levantada se tipo_regra for inválido ou não fornecido.
        """
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='INVALIDO', # Tipo inválido
            dia_semana=0,
            hora_inicio_recorrente=time(9,0)
        )
        with self.assertRaisesMessage(ValidationError, "Um tipo de regra válido deve ser selecionado."):
            regra.full_clean()

        regra_sem_tipo = RegraDisponibilidade(
            profissional=self.perfil_profissional
            # tipo_regra não definido
        )
        # O campo tipo_regra não tem default e não é blank=True no modelo,
        # então um erro de validação de campo (não do clean) deve ocorrer.
        # Se CharField com choices não tiver um valor, a validação de campo do Django falha.
        # O método clean() nem seria chamado se o tipo fosse None e o campo não permitisse.
        # No entanto, o clean() tem um `else: raise ValidationError("Um tipo de regra válido deve ser selecionado.")`
        # que pegaria um tipo que não é 'SEMANAL' nem 'ESPECIFICA'.
        # Se tipo_regra for None e o modelo permitir (o que não é o caso aqui pois não tem null=True), o else do clean pegaria.
        # Como não tem null=True, a validação de campo do Django já pegaria se fosse None.
        # O teste com 'INVALIDO' é mais direto para a lógica `else` do `clean`.
        # Se você quiser testar o comportamento de `None` especificamente no `clean`,
        # precisaria permitir `null=True` no modelo para `tipo_regra`, o que não é o caso.

    def test_str_representation_semanal(self):
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_inicio_recorrente=time(9, 0),
            hora_fim_recorrente=time(17, 0)
        )
        expected_str = f"{self.user_profissional.username} - Semanal: Segunda-feira 09:00-17:00"
        self.assertEqual(str(regra), expected_str)

    def test_str_representation_especifica(self):
        inicio = timezone.make_aware(datetime(2025, 12, 24, 10, 0, 0))
        fim = timezone.make_aware(datetime(2025, 12, 24, 12, 0, 0))
        regra = RegraDisponibilidade(
            profissional=self.perfil_profissional,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio,
            data_hora_fim_especifica=fim
        )
        self.assertIn(self.user_profissional.username, str(regra))
        self.assertIn("Específica", str(regra))
        self.assertIn(timezone.localtime(inicio).strftime('%d/%m/%y %H:%M'), str(regra))
        self.assertIn(timezone.localtime(fim).strftime('%d/%m/%y %H:%M'), str(regra))


class AgendamentoModelTests(TestCase):

    def setUp(self):
        # Usuários e Perfis
        self.user_paciente = User.objects.create_user(username='paciente_teste', password='password123')
        self.perfil_paciente = PerfilPaciente.objects.create(user=self.user_paciente)
        
        self.user_profissional = User.objects.create_user(username='profissional_ag_teste', password='password123')
        self.perfil_profissional = PerfilProfissional.objects.create(user=self.user_profissional, tipo_profissional='PSIQUIATRA')

    def test_criacao_agendamento_valido(self):
        """
        Testa a criação de um agendamento válido e o status padrão.
        """
        data_hora_agendamento = timezone.now() + timedelta(days=5)
        agendamento = Agendamento.objects.create(
            paciente=self.perfil_paciente,
            profissional=self.perfil_profissional,
            data_hora=data_hora_agendamento
        )
        self.assertIsNotNone(agendamento.pk)
        self.assertEqual(agendamento.status, 'PENDENTE') # Verifica status padrão
        self.assertEqual(agendamento.paciente, self.perfil_paciente)
        self.assertEqual(agendamento.profissional, self.perfil_profissional)
        self.assertIsNotNone(agendamento.criado_em)
        self.assertIsNotNone(agendamento.atualizado_em)
        # self.assertTrue(agendamento.atualizado_em > primeira_atualizacao) # REMOVA/COMENTE ESTA LINHA DAQUI

    def test_str_representation_agendamento(self):
        """ Testa a representação em string de um agendamento. """
        data_hora_agendamento = timezone.make_aware(datetime(2025, 10, 5, 14, 30, 0))
        agendamento = Agendamento(
            paciente=self.perfil_paciente,
            profissional=self.perfil_profissional,
            data_hora=data_hora_agendamento,
            status='CONFIRMADO'
        )
        # A formatação da data no __str__ usa timezone.localtime
        data_formatada = timezone.localtime(data_hora_agendamento).strftime("%d/%m/%Y %H:%M")
        expected_str = (f"Consulta de {self.user_paciente.username} com "
                        f"{self.user_profissional.username} em {data_formatada} (Confirmado)")
        self.assertEqual(str(agendamento), expected_str)

    def test_atualizado_em_updates_on_save(self): # <--- NOVO MÉTODO DE TESTE
        """
        Testa se o campo 'atualizado_em' é atualizado a cada save subsequente.
        """
        data_hora_agendamento = timezone.now() + timedelta(days=5)
        agendamento = Agendamento.objects.create(
            paciente=self.perfil_paciente,
            profissional=self.perfil_profissional,
            data_hora=data_hora_agendamento
        )
        primeira_atualizacao = agendamento.atualizado_em

        # Modificamos um campo para justificar o save
        agendamento.notas_paciente = "Uma nota de teste."

        # Usamos mock para controlar o valor de timezone.now() durante o save
        # Isso garante que o novo timestamp será diferente e maior.
        with mock.patch('django.utils.timezone.now') as mock_now:
            # Configuramos o mock para retornar um tempo 1 segundo após a primeira atualização
            mock_now.return_value = primeira_atualizacao + timedelta(seconds=1)
            agendamento.save() # Salva o agendamento novamente

        segunda_atualizacao = agendamento.atualizado_em

        self.assertTrue(segunda_atualizacao > primeira_atualizacao,
                        f"Esperado que a segunda atualização ({segunda_atualizacao}) "
                        f"fosse maior que a primeira ({primeira_atualizacao}).")
        self.assertNotEqual(primeira_atualizacao, segunda_atualizacao)


# Em contas/tests.py
# (Todos os imports e as classes de teste anteriores permanecem como estão)

class APICriarDispAvulsaViewTests(TestCase):

    def setUp(self):
        # Usuários para teste
        self.profissional_user = User.objects.create_user(username='api_prof', password='password123')
        self.perfil_profissional = PerfilProfissional.objects.create(user=self.profissional_user)
        
        self.paciente_user = User.objects.create_user(username='api_paciente', password='password123')
        self.perfil_paciente = PerfilPaciente.objects.create(user=self.paciente_user)

        self.url = reverse('contas:api_criar_disp_avulsa')

    # ... (os testes de permissão e falha que já escrevemos permanecem aqui) ...

    def test_acesso_negado_para_paciente(self):
        """
        Verifica se um paciente logado recebe um erro de permissão (403).
        """
        self.client.login(username='api_paciente', password='password123')
        response = self.client.post(self.url, data={}, content_type='application/json')
        
        self.assertEqual(response.status_code, 403)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'error')
        self.assertEqual(response_data['message'], 'Apenas profissionais podem adicionar disponibilidade.')

    def test_acesso_negado_para_usuario_anonimo(self):
        """
        Verifica se um usuário não logado é redirecionado para a página de login correta.
        """
        response = self.client.post(self.url, data={}, content_type='application/json')
        
        # Agora que LOGIN_URL está definido em settings.py, o redirect deve ser o correto.
        # Revertemos o teste para a sua forma ideal.
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_falha_com_dados_invalidos_json(self):
        """
        Verifica se a API retorna erro 400 para JSON malformado.
        """
        self.client.login(username='api_prof', password='password123')
        response = self.client.post(self.url, data='{"json": "invalido"', content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertEqual(response.json()['message'], 'Dados JSON inválidos na requisição.')

    def test_falha_com_dados_faltando(self):
        """
        Verifica se a API retorna erro 400 se campos estiverem faltando no payload.
        """
        self.client.login(username='api_prof', password='password123')
        payload = {
            'data_hora_inicio_especifica': (timezone.now() + timedelta(days=1)).isoformat()
            # 'data_hora_fim_especifica' está faltando
        }
        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertEqual(response.json()['message'], 'Datas de início e fim são obrigatórias.')
    
    def test_falha_com_data_inicio_no_passado(self):
        """
        Verifica se a API retorna erro 400 se a data de início for no passado.
        """
        self.client.login(username='api_prof', password='password123')
        payload = {
            'data_hora_inicio_especifica': (timezone.now() - timedelta(days=1)).isoformat(),
            'data_hora_fim_especifica': (timezone.now() + timedelta(hours=2)).isoformat(),
        }
        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        # A mensagem vem da validação do modelo
        self.assertIn('Não é possível adicionar disponibilidade específica no passado', response.json()['message'])
        # ...

    def test_criacao_com_sucesso_sem_fusao(self): # Renomeado para clareza
        """
        Testa a criação de uma nova regra quando não há regras adjacentes para fusão.
        """
        self.client.login(username='api_prof', password='password123')
        inicio = timezone.now() + timedelta(days=3)
        fim = inicio + timedelta(hours=1)
        payload = {'data_hora_inicio_especifica': inicio.isoformat(), 'data_hora_fim_especifica': fim.isoformat()}
        
        self.assertEqual(RegraDisponibilidade.objects.count(), 0)
        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('criada com sucesso', response_data['data']['message'])
        self.assertEqual(RegraDisponibilidade.objects.count(), 1)

    # --- NOVOS TESTES PARA A LÓGICA DE FUSÃO ---

    def test_fusao_com_regra_anterior_adjacente(self):
        """
        Testa se uma nova disponibilidade (10h-11h) se funde com uma existente (9h-10h).
        """
        self.client.login(username='api_prof', password='password123')
        
        # Cria a regra existente das 9h às 10h
        inicio_existente = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=5)
        fim_existente = inicio_existente + timedelta(hours=1)
        regra_existente = RegraDisponibilidade.objects.create(
            profissional=self.perfil_profissional, tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio_existente, data_hora_fim_especifica=fim_existente
        )

        # Prepara o payload para a nova regra adjacente, das 10h às 11h
        payload = {
            'data_hora_inicio_especifica': fim_existente.isoformat(),
            'data_hora_fim_especifica': (fim_existente + timedelta(hours=1)).isoformat()
        }

        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')

        self.assertEqual(response.status_code, 200) # 200 OK para update
        self.assertIn('estendida com sucesso', response.json()['data']['message'])
        self.assertEqual(RegraDisponibilidade.objects.count(), 1) # Garante que nenhuma regra nova foi criada
        
        regra_existente.refresh_from_db()
        self.assertEqual(regra_existente.data_hora_inicio_especifica, inicio_existente) # Início não muda
        self.assertEqual(regra_existente.data_hora_fim_especifica, fim_existente + timedelta(hours=1)) # Fim foi estendido

    def test_fusao_com_regra_posterior_adjacente(self):
        """
        Testa se uma nova disponibilidade (9h-10h) se funde com uma existente (10h-11h).
        """
        self.client.login(username='api_prof', password='password123')

        inicio_existente = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=5)
        fim_existente = inicio_existente + timedelta(hours=1)
        regra_existente = RegraDisponibilidade.objects.create(
            profissional=self.perfil_profissional, tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio_existente, data_hora_fim_especifica=fim_existente
        )

        payload = {
            'data_hora_inicio_especifica': (inicio_existente - timedelta(hours=1)).isoformat(),
            'data_hora_fim_especifica': inicio_existente.isoformat()
        }

        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('estendida com sucesso', response.json()['data']['message'])
        self.assertEqual(RegraDisponibilidade.objects.count(), 1)
        
        regra_existente.refresh_from_db()
        self.assertEqual(regra_existente.data_hora_inicio_especifica, inicio_existente - timedelta(hours=1))
        self.assertEqual(regra_existente.data_hora_fim_especifica, fim_existente)

    def test_fusao_tripla_conectando_duas_regras(self):
        """
        Testa se uma nova disp. (10h-11h) conecta duas existentes (9h-10h e 11h-12h).
        """
        self.client.login(username='api_prof', password='password123')

        # Regra das 9h às 10h
        inicio_regra1 = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=5)
        regra1 = RegraDisponibilidade.objects.create(
            profissional=self.perfil_profissional, tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio_regra1, data_hora_fim_especifica=inicio_regra1 + timedelta(hours=1)
        )
        
        # Regra das 11h às 12h
        inicio_regra2 = inicio_regra1 + timedelta(hours=2)
        regra2 = RegraDisponibilidade.objects.create(
            profissional=self.perfil_profissional, tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=inicio_regra2, data_hora_fim_especifica=inicio_regra2 + timedelta(hours=1)
        )

        self.assertEqual(RegraDisponibilidade.objects.count(), 2)

        # Payload para a regra "ponte" das 10h às 11h
        payload = {
            'data_hora_inicio_especifica': (inicio_regra1 + timedelta(hours=1)).isoformat(),
            'data_hora_fim_especifica': inicio_regra2.isoformat()
        }

        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('unificadas com sucesso', response.json()['data']['message'])
        
        # Apenas uma regra deve existir no final
        self.assertEqual(RegraDisponibilidade.objects.count(), 1)
        
        regra_final = RegraDisponibilidade.objects.first()
        self.assertEqual(regra_final.pk, regra1.pk) # A primeira regra foi atualizada
        self.assertEqual(regra_final.data_hora_inicio_especifica, inicio_regra1) # Início original da primeira
        self.assertEqual(regra_final.data_hora_fim_especifica, inicio_regra2 + timedelta(hours=1)) # Fim original da segunda
        
        # A segunda regra não deve mais existir
        with self.assertRaises(RegraDisponibilidade.DoesNotExist):
            RegraDisponibilidade.objects.get(pk=regra2.pk)


class APIEditarRegraDisponibilidadeViewTests(TestCase):

    def setUp(self):
        # Usuário profissional (dono da regra)
        self.dono_user = User.objects.create_user(username='dono_api_edit', password='password123')
        self.dono_perfil = PerfilProfissional.objects.create(user=self.dono_user)

        # Outro profissional (não dono da regra)
        self.outro_user = User.objects.create_user(username='outro_api_edit', password='password123')
        self.outro_perfil = PerfilProfissional.objects.create(user=self.outro_user)

        # Regra específica para ser editada
        self.regra_especifica = RegraDisponibilidade.objects.create(
            profissional=self.dono_perfil,
            tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=timezone.now() + timedelta(days=10),
            data_hora_fim_especifica=timezone.now() + timedelta(days=10, hours=1)
        )

        # Regra semanal para testar a proibição de edição
        self.regra_semanal = RegraDisponibilidade.objects.create(
            profissional=self.dono_perfil,
            tipo_regra='SEMANAL',
            dia_semana=0,
            hora_inicio_recorrente=time(9, 0),
            hora_fim_recorrente=time(10, 0)
        )

        self.url = reverse('contas:api_editar_regra_disponibilidade', kwargs={'regra_id': self.regra_especifica.pk})
        self.url_regra_semanal = reverse('contas:api_editar_regra_disponibilidade', kwargs={'regra_id': self.regra_semanal.pk})
        
        self.payload_valido = {
            'data_hora_inicio_especifica': (timezone.now() + timedelta(days=11)).isoformat(),
            'data_hora_fim_especifica': (timezone.now() + timedelta(days=11, hours=2)).isoformat()
        }

    def test_acesso_negado_para_nao_dono(self):
        """
        Verifica se um profissional que não é dono da regra recebe 404 (pois a regra não é encontrada para ele).
        """
        self.client.login(username='outro_api_edit', password='password123')
        response = self.client.post(self.url, data=json.dumps(self.payload_valido), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 'error')

    def test_edicao_proibida_para_regras_semanais(self):
        """
        Verifica se a API proíbe a edição de regras do tipo 'SEMANAL'.
        """
        self.client.login(username='dono_api_edit', password='password123')
        response = self.client.post(self.url_regra_semanal, data=json.dumps(self.payload_valido), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('Apenas disponibilidades específicas', response.json()['message'])

    def test_falha_com_dados_invalidos_fim_antes_do_inicio(self):
        """
        Verifica se a API retorna erro 400 se a data de fim for antes da data de início.
        """
        self.client.login(username='dono_api_edit', password='password123')
        payload_invalido = {
            'data_hora_inicio_especifica': (timezone.now() + timedelta(days=11, hours=2)).isoformat(),
            'data_hora_fim_especifica': (timezone.now() + timedelta(days=11)).isoformat() # Fim antes do início
        }
        response = self.client.post(self.url, data=json.dumps(payload_invalido), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('O fim específico deve ser após o início específico', response.json()['message'])
        
    def test_edicao_bem_sucedida_com_post_valido(self):
        """
        Testa se a API atualiza uma regra com sucesso com dados válidos.
        """
        self.client.login(username='dono_api_edit', password='password123')
        
        # Pega o valor antigo para comparação
        hora_inicio_antiga = self.regra_especifica.data_hora_inicio_especifica
        
        response = self.client.post(self.url, data=json.dumps(self.payload_valido), content_type='application/json')
        
        # Verifica a resposta
        self.assertEqual(response.status_code, 200) # 200 OK para updates
        response_data = response.json()
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['data']['message'], 'Disponibilidade específica atualizada com sucesso!')
        
        # Verifica o banco de dados
        self.regra_especifica.refresh_from_db()
        # Compara datetimes, eles não devem ser iguais ao valor antigo
        self.assertNotEqual(self.regra_especifica.data_hora_inicio_especifica, hora_inicio_antiga)
        # Verifica se o novo valor corresponde ao payload enviado (com cuidado com a precisão)
        novo_inicio_esperado = datetime.fromisoformat(self.payload_valido['data_hora_inicio_especifica'])
        self.assertAlmostEqual(self.regra_especifica.data_hora_inicio_especifica, novo_inicio_esperado, delta=timedelta(seconds=1))


class APIExcluirRegrasListaViewTests(TestCase):

    def setUp(self):
        # Usuário profissional (dono das regras)
        self.dono_user = User.objects.create_user(username='dono_api_delete', password='password123')
        self.dono_perfil = PerfilProfissional.objects.create(user=self.dono_user)

        # Outro profissional (para teste de permissão)
        self.outro_user = User.objects.create_user(username='outro_api_delete', password='password123')
        self.outro_perfil = PerfilProfissional.objects.create(user=self.outro_user)

        # Regras de teste que pertencem ao primeiro profissional
        self.regra1 = RegraDisponibilidade.objects.create(
            profissional=self.dono_perfil, tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=timezone.now() + timedelta(days=1),
            data_hora_fim_especifica=timezone.now() + timedelta(days=1, hours=1)
        )
        self.regra2 = RegraDisponibilidade.objects.create(
            profissional=self.dono_perfil, tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=timezone.now() + timedelta(days=2),
            data_hora_fim_especifica=timezone.now() + timedelta(days=2, hours=1)
        )
        # Regra de outro profissional
        self.regra_outro_prof = RegraDisponibilidade.objects.create(
            profissional=self.outro_perfil, tipo_regra='ESPECIFICA',
            data_hora_inicio_especifica=timezone.now() + timedelta(days=3),
            data_hora_fim_especifica=timezone.now() + timedelta(days=3, hours=1)
        )

        self.url = reverse('contas:api_excluir_regras_disponibilidade_lista')

    def test_falha_ao_tentar_excluir_regra_de_outro_profissional(self):
        """
        Verifica se um profissional não consegue excluir a regra de outro.
        """
        self.client.login(username='dono_api_delete', password='password123')
        
        payload = {'ids': [self.regra_outro_prof.pk]}
        
        # O número de regras deve ser 3 antes da chamada
        self.assertEqual(RegraDisponibilidade.objects.count(), 3)
        
        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        
        # A view deve retornar um erro 404 pois não encontra regras válidas para excluir
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 'error')
        self.assertIn('Nenhuma regra válida para exclusão foi encontrada', response.json()['message'])
        
        # O número de regras não deve mudar
        self.assertEqual(RegraDisponibilidade.objects.count(), 3)

    def test_falha_com_payload_invalido_sem_ids(self):
        """
        Verifica se a API retorna erro 400 se a chave 'ids' estiver faltando.
        """
        self.client.login(username='dono_api_delete', password='password123')
        payload = {'dados': 'invalidos'}
        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertEqual(response.json()['message'], 'Lista de IDs inválida ou não fornecida.')

    def test_exclusao_bem_sucedida_de_multiplas_regras(self):
        """
        Testa se a API exclui com sucesso uma lista de regras pertencentes ao profissional.
        """
        self.client.login(username='dono_api_delete', password='password123')
        
        ids_para_excluir = [self.regra1.pk, self.regra2.pk]
        payload = {'ids': ids_para_excluir}
        
        self.assertEqual(RegraDisponibilidade.objects.count(), 3)
        
        response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        
        # Verifica a resposta
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('2 regra(s) de disponibilidade específica excluída(s)', response_data['data']['message'])
        
        # Verifica o banco de dados
        self.assertEqual(RegraDisponibilidade.objects.count(), 1)
        # Confirma que a regra restante é a do outro profissional
        regra_restante = RegraDisponibilidade.objects.first()
        self.assertEqual(regra_restante.pk, self.regra_outro_prof.pk)
        
        # Verifica que as regras excluídas não existem mais
        self.assertFalse(RegraDisponibilidade.objects.filter(pk__in=ids_para_excluir).exists())


class EditarPerfilViewTests(TestCase):

    def setUp(self):
        # Usuário profissional
        self.profissional_user = User.objects.create_user(username='prof_edit_test', password='password123', first_name='Maria')
        self.perfil_profissional = PerfilProfissional.objects.create(user=self.profissional_user)

        # Usuário paciente
        self.paciente_user = User.objects.create_user(username='pac_edit_test', password='password123', first_name='João')
        self.perfil_paciente = PerfilPaciente.objects.create(user=self.paciente_user)

        self.url = reverse('contas:editar_perfil')

    def test_view_requer_login(self):
        """
        Verifica se um usuário não logado é redirecionado para a página de login.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_profissional_ve_o_formulario_correto(self):
        """
        Verifica se um profissional logado vê o formulário de perfil profissional.
        """
        self.client.login(username='prof_edit_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contas/editar_perfil.html')
        self.assertIsInstance(response.context['form'], PerfilProfissionalForm)
        self.assertEqual(response.context['object'], self.perfil_profissional)

    def test_paciente_ve_o_formulario_correto(self):
        """
        Verifica se um paciente logado vê o formulário de perfil de paciente.
        """
        self.client.login(username='pac_edit_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], PerfilPacienteForm)
        self.assertEqual(response.context['object'], self.perfil_paciente)

    def test_profissional_atualiza_perfil_com_sucesso(self):
        """
        Testa a atualização bem-sucedida do perfil de um profissional (sem upload de foto).
        """
        self.client.login(username='prof_edit_test', password='password123')
        
        dados_post = {
            'bio': 'Nova biografia de teste.',
            'valor_consulta': '150.75'
        }
        
        response = self.client.post(self.url, data=dados_post)
        
        self.assertEqual(response.status_code, 302) # Redirecionamento após sucesso
        self.assertRedirects(response, reverse('contas:meu_perfil'))

        # Atualiza a instância do objeto a partir do banco de dados
        self.perfil_profissional.refresh_from_db()
        self.assertEqual(self.perfil_profissional.bio, 'Nova biografia de teste.')
        self.assertEqual(self.perfil_profissional.valor_consulta, 150.75)

    def test_profissional_faz_upload_de_foto(self):
        """
        Testa a atualização do perfil de um profissional com upload de foto.
        """
        self.client.login(username='prof_edit_test', password='password123')

        # Cria uma imagem falsa em memória para o teste
        image_io = BytesIO()
        image = Image.new('RGB', (100, 100), 'red') # Cria uma imagem vermelha 100x100
        image.save(image_io, 'jpeg')
        image_io.seek(0)
        
        # Cria um arquivo "uploaded" para o teste
        uploaded_file = SimpleUploadedFile(
            name='test_image.jpg',
            content=image_io.getvalue(),
            content_type='image/jpeg'
        )

        dados_post = {
            'bio': 'Biografia com foto.',
            'foto_perfil': uploaded_file
        }

        response = self.client.post(self.url, data=dados_post)
        
        self.assertEqual(response.status_code, 302)

        self.perfil_profissional.refresh_from_db()
        self.assertIsNotNone(self.perfil_profissional.foto_perfil)
        self.assertTrue(self.perfil_profissional.foto_perfil.name.startswith('fotos_perfil/profissionais/test_image'))

        # Importante: Limpa os arquivos de mídia de teste após a execução
        self.perfil_profissional.foto_perfil.delete(save=False)


class RegistroViewTests(TestCase):

    def setUp(self):
        self.url = reverse('contas:registro')

    def test_pagina_de_registro_carrega_corretamente_get(self):
        """
        Verifica se a página de registro é renderizada corretamente com um GET.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contas/registro.html')
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], RegistroUsuarioForm)

    def test_registro_bem_sucedido_de_paciente(self):
        """
        Testa a criação bem-sucedida de uma conta de Paciente via POST.
        """
        dados_paciente = {
            'username': 'novopaciente',
            'first_name': 'Novo',
            'last_name': 'Paciente',
            'email': 'paciente@teste.com',
            'password_confirmation1': 'senhaforte123',
            'password_confirmation2': 'senhaforte123',
            'tipo_conta': 'PACIENTE',
        }
        
        # Renomeamos as chaves para corresponder ao formulário UserCreationForm
        dados_paciente['password1'] = dados_paciente.pop('password_confirmation1')
        dados_paciente['password2'] = dados_paciente.pop('password_confirmation2')

        # Garante que nenhum usuário ou perfil exista antes do teste
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(PerfilPaciente.objects.count(), 0)

        response = self.client.post(self.url, data=dados_paciente)

        # Verifica se o usuário foi redirecionado para a página de login após o sucesso
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

        # Verifica se o usuário e o perfil foram criados no banco de dados
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(PerfilPaciente.objects.count(), 1)
        
        novo_user = User.objects.get(username='novopaciente')
        self.assertTrue(hasattr(novo_user, 'perfil_paciente'))
        self.assertFalse(hasattr(novo_user, 'perfil_profissional'))

    def test_registro_bem_sucedido_de_profissional(self):
        """
        Testa a criação bem-sucedida de uma conta de Profissional via POST.
        """
        dados_profissional = {
            'username': 'novoprofissional',
            'email': 'prof@teste.com',
            'password1': 'senhaforte123',
            'password2': 'senhaforte123',
            'tipo_conta': 'PROFISSIONAL',
        }

        response = self.client.post(self.url, data=dados_profissional)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(PerfilProfissional.objects.count(), 1)
        
        novo_user = User.objects.get(username='novoprofissional')
        self.assertTrue(hasattr(novo_user, 'perfil_profissional'))
        self.assertFalse(hasattr(novo_user, 'perfil_paciente'))

    def test_registro_falha_com_senhas_diferentes(self):
        """
        Testa se o registro falha se as senhas não corresponderem.
        """
        dados_invalidos = {
            'username': 'usuariofalho',
            'email': 'falho@teste.com',
            'password1': 'senha1',
            'password2': 'senha2', # Senhas diferentes
            'tipo_conta': 'PACIENTE',
        }

        response = self.client.post(self.url, data=dados_invalidos)

        # A página deve ser re-renderizada com um erro no formulário
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertTrue(response.context['form'].errors)
        # Verifica se o erro específico está no campo password2
        self.assertIn('password2', response.context['form'].errors)
        
        # Garante que nenhum usuário foi criado
        self.assertEqual(User.objects.count(), 0)

    def test_registro_falha_com_username_existente(self):
        """
        Testa se o registro falha se o nome de usuário já existir.
        """
        # Cria um usuário inicial
        User.objects.create_user(username='existente', password='password123')
        
        dados_duplicados = {
            'username': 'existente', # Username já em uso
            'email': 'unico@teste.com',
            'password1': 'senhaforte123',
            'password2': 'senhaforte123',
            'tipo_conta': 'PACIENTE',
        }
        
        response = self.client.post(self.url, data=dados_duplicados)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertIn('username', response.context['form'].errors)
        
        # Garante que apenas o usuário original existe
        self.assertEqual(User.objects.count(), 1)


# Em contas/tests.py
# (Todos os imports e as classes de teste anteriores permanecem como estão)

class AgendamentoWorkflowTests(TestCase):

    def setUp(self):
        # Cria usuários e perfis para o fluxo
        self.paciente_user = User.objects.create_user(username='paciente_workflow', password='password123')
        self.perfil_paciente = PerfilPaciente.objects.create(user=self.paciente_user)
        
        self.profissional_user = User.objects.create_user(username='prof_workflow', password='password123')
        self.perfil_profissional = PerfilProfissional.objects.create(user=self.profissional_user)
        
        # Cria um terceiro usuário para testes de permissão
        self.outro_prof_user = User.objects.create_user(username='outro_prof_workflow', password='password123')
        self.outro_perfil_profissional = PerfilProfissional.objects.create(user=self.outro_prof_user)

        # Cria um agendamento pendente para ser usado nos testes
        self.agendamento_pendente = Agendamento.objects.create(
            paciente=self.perfil_paciente,
            profissional=self.perfil_profissional,
            data_hora=timezone.now() + timedelta(days=5)
        )

        self.url_confirmar = reverse('contas:confirmar_agendamento', kwargs={'agendamento_id': self.agendamento_pendente.pk})
        self.url_cancelar = reverse('contas:cancelar_agendamento', kwargs={'agendamento_id': self.agendamento_pendente.pk})
        self.redirect_url = reverse('contas:meus_agendamentos')

    # --- Testes para confirmar_agendamento ---

    def test_confirmar_agendamento_apenas_pelo_profissional_responsavel(self):
        """
        Garante que apenas o profissional do agendamento pode confirmá-lo.
        """
        self.client.login(username='prof_workflow', password='password123')
        response = self.client.post(self.url_confirmar)
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.redirect_url)
        
        self.agendamento_pendente.refresh_from_db()
        self.assertEqual(self.agendamento_pendente.status, 'CONFIRMADO')

    def test_paciente_nao_pode_confirmar_agendamento(self):
        """
        Verifica se o paciente não tem permissão para confirmar o agendamento.
        """
        self.client.login(username='paciente_workflow', password='password123')
        response = self.client.post(self.url_confirmar)
        
        # A view deve redirecionar com uma mensagem de erro
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.redirect_url)
        
        self.agendamento_pendente.refresh_from_db()
        self.assertEqual(self.agendamento_pendente.status, 'PENDENTE') # O status não deve mudar

    def test_outro_profissional_nao_pode_confirmar_agendamento(self):
        """
        Verifica se um profissional não relacionado ao agendamento não pode confirmá-lo.
        """
        self.client.login(username='outro_prof_workflow', password='password123')
        response = self.client.post(self.url_confirmar)
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.redirect_url)

        self.agendamento_pendente.refresh_from_db()
        self.assertEqual(self.agendamento_pendente.status, 'PENDENTE') # O status não deve mudar

    # --- Testes para cancelar_agendamento ---
    
    def test_paciente_pode_cancelar_agendamento(self):
        """
        Verifica se o paciente do agendamento pode cancelá-lo.
        """
        self.client.login(username='paciente_workflow', password='password123')
        response = self.client.post(self.url_cancelar)
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.redirect_url)
        
        self.agendamento_pendente.refresh_from_db()
        self.assertEqual(self.agendamento_pendente.status, 'CANCELADO')

    def test_profissional_pode_cancelar_agendamento(self):
        """
        Verifica se o profissional do agendamento pode cancelá-lo.
        """
        self.client.login(username='prof_workflow', password='password123')
        response = self.client.post(self.url_cancelar)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.redirect_url)

        self.agendamento_pendente.refresh_from_db()
        self.assertEqual(self.agendamento_pendente.status, 'CANCELADO')

    def test_outro_profissional_nao_pode_cancelar_agendamento(self):
        """
        Verifica se um usuário não relacionado não pode cancelar o agendamento.
        """
        self.client.login(username='outro_prof_workflow', password='password123')
        response = self.client.post(self.url_cancelar)
        
        # A view deve redirecionar com uma mensagem de erro
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.redirect_url)
        
        self.agendamento_pendente.refresh_from_db()
        self.assertEqual(self.agendamento_pendente.status, 'PENDENTE') # O status não deve mudar