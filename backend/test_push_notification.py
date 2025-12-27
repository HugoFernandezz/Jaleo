#!/usr/bin/env python3
"""
Script para enviar notificaciones push de prueba usando Expo Push API
"""
import requests
import json
import sys

def send_test_notification(token):
    """
    Envía una notificación push de prueba usando Expo Push API
    
    Args:
        token: Token de Expo Push (formato: ExponentPushToken[...])
    """
    url = "https://exp.host/--/api/v2/push/send"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }
    
    message = {
        "to": token,
        "sound": "default",
        "title": "🧪 Test de Notificación Push",
        "body": "Esta es una notificación push de prueba desde el servidor",
        "data": {
            "test": True,
            "timestamp": "2024-12-20"
        },
        "priority": "high",
        "channelId": "default"
    }
    
    print(f"[*] Enviando notificacion push a: {token}")
    print(f"[*] URL: {url}")
    print(f"[*] Mensaje: {json.dumps(message, indent=2)}")
    print("\n" + "="*50 + "\n")
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(message), timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            data = result.get('data', {})
            
            # Manejar respuesta como lista (múltiples tokens) o objeto (un token)
            if isinstance(data, list) and len(data) > 0:
                status = data[0].get('status')
                if status == 'ok':
                    print("[OK] Notificacion enviada correctamente!")
                    print(f"[*] ID: {data[0].get('id', 'N/A')}")
                    return True
                else:
                    print(f"[ERROR] Error al enviar notificacion: {status}")
                    print(f"[*] Detalles: {json.dumps(data[0], indent=2)}")
                    return False
            elif isinstance(data, dict):
                # Respuesta como objeto único
                status = data.get('status')
                if status == 'ok':
                    print("[OK] Notificacion enviada correctamente!")
                    print(f"[*] ID: {data.get('id', 'N/A')}")
                    return True
                else:
                    print(f"[ERROR] Error al enviar notificacion: {status}")
                    print(f"[*] Detalles: {json.dumps(data, indent=2)}")
                    return False
            else:
                print("[ERROR] Respuesta inesperada:")
                print(json.dumps(result, indent=2))
                return False
        else:
            print(f"[ERROR] Error HTTP {response.status_code}:")
            print(response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error de conexion: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("="*50)
        print("Script de Prueba de Notificaciones Push")
        print("="*50)
        print("\nUso:")
        print("  python test_push_notification.py <EXPO_PUSH_TOKEN>")
        print("\nEjemplo:")
        print("  python test_push_notification.py ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]")
        print("\n" + "="*50)
        print("\nPara obtener el token:")
        print("  1. Abre la app en tu dispositivo fisico")
        print("  2. Revisa la consola de desarrollo")
        print("  3. Busca el mensaje: 'Token para test:' o 'FCM Token:'")
        print("  4. Copia el token completo (incluyendo ExponentPushToken[...])")
        print("\nTip: El token tambien se guarda en AsyncStorage")
        print("   Puedes agregar un boton temporal en la app para mostrarlo")
        print("="*50)
        sys.exit(1)
    
    token = sys.argv[1]
    
    # Validar formato básico
    if not token.startswith('ExponentPushToken[') or not token.endswith(']'):
        print("[ADVERTENCIA] El token no parece tener el formato correcto")
        print("   Formato esperado: ExponentPushToken[...]")
        print("   Continuar de todas formas? (s/n): ", end='')
        respuesta = input().strip().lower()
        if respuesta != 's':
            print("[CANCELADO]")
            sys.exit(1)
    
    success = send_test_notification(token)
    sys.exit(0 if success else 1)

