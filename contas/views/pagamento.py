from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings
from datetime import datetime
import stripe

from ..models import Agendamento


@login_required
def processar_pagamento(request, agendamento_id):
    """View para processar pagamento do agendamento"""
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


@csrf_exempt
def stripe_webhook(request):
    """Webhook do Stripe para processar eventos de pagamento"""
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
        payment_intent = event['data']['object']
        
        # Busca o ID do nosso agendamento que guardamos nos metadados
        agendamento_id = payment_intent['metadata'].get('agendamento_id')
        
        try:
            agendamento = Agendamento.objects.get(id=agendamento_id)  # type: ignore
            
            # Atualiza o status do pagamento e do agendamento
            agendamento.status_pagamento = 'PAGO'
            agendamento.status = 'CONFIRMADO'
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