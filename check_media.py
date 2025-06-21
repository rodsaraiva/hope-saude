#!/usr/bin/env python
"""
Script simples para verificar se as pastas de mídia existem.
"""

import os

def check_media_folders():
    """Verifica se as pastas de mídia existem"""
    
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
    
    print("Verificando pastas de mídia...")
    print(f"Diretório base: {base_dir}")
    print(f"Pasta media: {media_root}")
    print("-" * 50)
    
    all_exist = True
    for directory in directories:
        if os.path.exists(directory):
            print(f"✅ Pasta existe: {directory}")
        else:
            print(f"❌ Pasta não existe: {directory}")
            all_exist = False
    
    print("-" * 50)
    if all_exist:
        print("✅ Todas as pastas de mídia existem!")
        return True
    else:
        print("⚠️  Algumas pastas de mídia não existem.")
        return False

if __name__ == '__main__':
    check_media_folders() 