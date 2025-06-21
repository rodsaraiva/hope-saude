#!/usr/bin/env python
"""
Script para criar as pastas de mídia necessárias.
Execute este script para garantir que todas as pastas existam.
"""

import os
import sys

# Adicionar o diretório do projeto ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meuprojeto.settings')

import django
django.setup()

def create_media_folders():
    """Cria todas as pastas de mídia necessárias"""
    
    # Obter o diretório base do projeto
    base_dir = os.path.dirname(os.path.abspath(__file__))
    media_root = os.path.join(base_dir, 'media')
    
    # Lista de pastas que precisam existir
    directories = [
        media_root,
        os.path.join(media_root, 'documentos'),
        os.path.join(media_root, 'fotos_perfil'),
        os.path.join(media_root, 'fotos_perfil', 'profissionais'),
        os.path.join(media_root, 'fotos_perfil', 'pacientes'),
    ]
    
    print("Criando pastas de mídia...")
    print(f"Diretório base: {base_dir}")
    print(f"Pasta media: {media_root}")
    print("-" * 50)
    
    for directory in directories:
        try:
            if not os.path.exists(directory):
                # Tentar com permissões normais primeiro
                os.makedirs(directory, mode=0o755, exist_ok=True)
                print(f"✅ Pasta criada: {directory}")
            else:
                print(f"ℹ️  Pasta já existe: {directory}")
        except PermissionError:
            try:
                # Se falhar, tentar com permissões mais permissivas
                os.makedirs(directory, mode=0o777, exist_ok=True)
                print(f"✅ Pasta criada (permissões especiais): {directory}")
            except Exception as e:
                print(f"❌ Erro ao criar pasta {directory}: {e}")
        except Exception as e:
            print(f"❌ Erro ao criar pasta {directory}: {e}")
    
    print("-" * 50)
    print("Verificação concluída!")
    
    # Verificar se todas as pastas foram criadas
    all_created = True
    for directory in directories:
        if not os.path.exists(directory):
            print(f"❌ Pasta não foi criada: {directory}")
            all_created = False
    
    if all_created:
        print("✅ Todas as pastas foram criadas com sucesso!")
    else:
        print("⚠️  Algumas pastas não puderam ser criadas.")
        print("Verifique as permissões do diretório do projeto.")

if __name__ == '__main__':
    create_media_folders() 