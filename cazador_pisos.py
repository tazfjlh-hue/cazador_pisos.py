import os
import imaplib
import email
import smtplib
from email.message import EmailMessage
from bs4 import BeautifulSoup
from google import genai

# Credenciales desde las variables de entorno (Secrets de GitHub)
EMAIL_USER = os.environ["EMAIL_USER"]         # El Gmail nuevo que recibe las alertas
EMAIL_PASS = os.environ["EMAIL_PASS"]         # La contraseña de aplicación de 16 letras
EMAIL_PERSONAL = os.environ["EMAIL_PERSONAL"] # Tu correo personal donde llegan las gangas
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"] # Tu clave gratuita de Google AI Studio

# Define aquí los precios medios (€/m2) de tus barrios objetivo
ZONAS_REFERENCIA = """
- Centro: 4.100 €/m2
- Ensanche: 3.400 €/m2
- Barrio Norte: 2.600 €/m2
"""

def limpiar_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    texto = soup.get_text(separator=" ", strip=True)
    enlaces = [
        a['href'] for a in soup.find_all('a', href=True)
        if '://idealista.com' in a['href'] or 'fotocasa.es' in a['href']
    ]
    return texto[:3500], list(set(enlaces))

def analizar_con_ia(texto_correo, enlaces):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Eres un inversor inmobiliario experto en España. Acabo de recibir esta alerta de un portal inmobiliario.
    
    Texto del correo: {texto_correo}
    Enlaces detectados: {enlaces}
    Precios medios de referencia: {ZONAS_REFERENCIA}
    
    Analiza los inmuebles que aparecen en el correo:
    1. Calcula el precio/m2 si aparecen los datos y compáralo con la referencia de la zona.
    2. Busca señales de oportunidad (ej. "a reformar", "urgente", "oportunidad", "bajada de precio", particular, terraza, buena altura).
    3. Descarta bajos interiores oscuros, nuda propiedad o pisos okupados.
    
    Si detectas al menos UN piso interesante o por debajo de mercado:
    - Empieza tu respuesta EXACTAMENTE con: OPORTUNIDAD
    - Resume: Zona, Precio, m2, por qué es buena oportunidad y pon el enlace directo limpio.
    
    Si NO hay nada interesante, responde únicamente: DESCARTADO
    """
    
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
    )
    return response.text.strip()

def enviar_aviso_correo(cuerpo_mensaje):
    msg = EmailMessage()
    msg.set_content(cuerpo_mensaje)
    msg["Subject"] = "🚨 Oportunidad Inmobiliaria Detectada"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_PERSONAL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

def revisar_correos():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")
    
    status, mensajes = mail.search(None, 'UNSEEN')
    ids_correos = mensajes[0].split()
    
    if not ids_correos:
        print("Sin correos nuevos por analizar.")
        mail.logout()
        return

    for num in ids_correos:
        status, datos = mail.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(datos[0][1])
        
        cuerpo_html = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    cuerpo_html = part.get_payload(decode=True).decode(errors="ignore")
                    break
        else:
            cuerpo_html = msg.get_payload(decode=True).decode(errors="ignore")
            
        if cuerpo_html:
            texto, enlaces = limpiar_html(cuerpo_html)
            veredicto = analizar_con_ia(texto, enlaces)
            
            if veredicto.startswith("OPORTUNIDAD"):
                enviar_aviso_correo(veredicto)
                print("¡Oportunidad encontrada! Correo enviado a tu bandeja personal.")
            else:
                print("Correo analizado y descartado.")
                
    mail.logout()

if __name__ == "__main__":
    revisar_correos()

