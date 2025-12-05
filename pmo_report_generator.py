#!/usr/bin/env python3
"""
PMO Bot - Jira para Slack
Envia relatórios automáticos do Jira para o Slack
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from base64 import b64encode
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configurações da API Jira
JIRA_EMAIL = os.environ.get('JIRA_EMAIL')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN')
JIRA_DOMAIN = 'ybymartech.atlassian.net'
JIRA_URL = f'https://{JIRA_DOMAIN}/rest/api/3'

# Slack Webhook
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

# Email Configuration
EMAIL_SENDER = os.environ.get('EMAIL_SENDER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'gmail')  # 'gmail' or 'outlook'
EMAIL_RECIPIENTS = os.environ.get('EMAIL_RECIPIENTS', '').split(',')

def get_date_range(mode='daily'):
    """Retorna o range de datas baseado no modo"""
    today = datetime.now()
    
    if mode == 'weekly':
        # Últimos 7 dias
        start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        return start_date, end_date, '📅 Relatório Semanal PMO'
    else:  # daily
        # Hoje
        start_date = today.strftime('%Y-%m-%d')
        end_date = start_date
        hour = today.hour
        
        if hour < 12:
            return start_date, end_date, '☀️ Dashboard Diário PMO - Manhã'
        else:
            return start_date, end_date, '🌆 Dashboard Diário PMO - Tarde'

def get_jira_issues(start_date, end_date):
    """Busca issues do Jira no período especificado"""
    
    # Credenciais encodadas em Base64
    credentials = b64encode(f'{JIRA_EMAIL}:{JIRA_API_TOKEN}'.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/json'
    }
    
    # JQL Query para buscar issues atualizadas no período
    jql = f'updated >= "{start_date}" AND updated <= "{end_date}" ORDER BY updated DESC'
    
    params = {
        'jql': jql,
        'maxResults': 100,
        'fields': 'summary,status,assignee,priority,created,updated'
    }
    
    try:
        response = requests.get(f'{JIRA_URL}/search', headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('issues', [])
    except Exception as e:
        print(f'Erro ao buscar issues: {e}')
        return []

def format_slack_message(issues, title, start_date, end_date):
    """Formata mensagem para o Slack"""
    
    # Contadores por status
    status_count = {}
    for issue in issues:
        status = issue['fields']['status']['name']
        status_count[status] = status_count.get(status, 0) + 1
    
    # Monta a mensagem
    blocks = [
        {
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': title
            }
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'*Período:* {start_date} até {end_date}\n*Total de issues:* {len(issues)}'
            }
        }
    ]
    
    # Lista últimas 5 issues
    if issues:
        blocks.append({
            'type': 'divider'
        })
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': '*Últimas issues atualizadas:*'
            }
        })
    
    for issue in issues[:5]:
        key = issue['key']
        summary = issue['fields']['summary']
        status = issue['fields']['status']['name']
        assignee = issue['fields'].get('assignee')
        assignee_name = assignee['displayName'] if assignee else 'Não atribuído'
        
        issue_url = f'https://{JIRA_DOMAIN}/browse/{key}'
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'*<{issue_url}|{key}>* - {summary}\n*Status:* {status} | *Responsável:* {assignee_name}'
            }
        })
    
    return {'blocks': blocks}

def send_to_slack(message):
    """Envia mensagem para o Slack"""
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message)
        response.raise_for_status()
        print('Mensagem enviada para o Slack com sucesso!')
        return True
    except Exception as e:
        print(f'Erro ao enviar mensagem para o Slack: {e}')
        return False

def send_email(issues, title, start_date, end_date):
    """Envia relatório por email"""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECIPIENTS:
        print('Email não configurado. Pulando envio.')
        return False
    
    try:
        # Criar mensagem de email em HTML
        msg = MIMEMultipart('alternative')
        msg['Subject'] = title
        msg['From'] = EMAIL_SENDER
        msg['To'] = ', '.join([r.strip() for r in EMAIL_RECIPIENTS if r.strip()])
        
        # Construir corpo do email em HTML
        html_body = f"""
        <html>
            <body style='font-family: Arial, sans-serif;'>
                <h2>{title}</h2>
                <p><strong>Período:</strong> {start_date} até {end_date}</p>
                <p><strong>Total de issues:</strong> {len(issues)}</p>
                
                <h3>Últimas issues atualizadas:</h3>
        """
        
        if issues:
            for issue in issues[:10]:
                key = issue['key']
                summary = issue['fields']['summary']
                status = issue['fields']['status']['name']
                assignee = issue['fields'].get('assignee')
                assignee_name = assignee['displayName'] if assignee else 'Não atribuído'
                issue_url = f'https://{JIRA_DOMAIN}/browse/{key}'
                
                html_body += f"""
                <p>
                    <strong><a href='{issue_url}'>{key}</a></strong> - {summary}<br>
                    <em>Status:</em> {status} | <em>Responsável:</em> {assignee_name}
                </p>
                """
        else:
            html_body += "<p>Nenhuma issue encontrada no período.</p>"
        
        html_body += """
            </body>
        </html>
        """
        
        # Anexar corpo HTML
        part = MIMEText(html_body, 'html')
        msg.attach(part)
        
        # Conectar ao servidor SMTP apropriado
        if EMAIL_PROVIDER.lower() == 'outlook':
            # Outlook/Office 365
            with smtplib.SMTP('smtp.office365.com', 587) as server:
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, [r.strip() for r in EMAIL_RECIPIENTS if r.strip()], msg.as_string())
                print(f'Email enviado com sucesso para {len(EMAIL_RECIPIENTS)} destinatário(s)!')
        else:
            # Gmail (padrão)
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, [r.strip() for r in EMAIL_RECIPIENTS if r.strip()], msg.as_string())
                print(f'Email enviado com sucesso para {len(EMAIL_RECIPIENTS)} destinatário(s)!')
        
        return True
    except Exception as e:
        print(f'Erro ao enviar email: {e}')
        return False

def main():
    """Função principal"""
    
    # Verifica variáveis de ambiente
    if not all([JIRA_EMAIL, JIRA_API_TOKEN, SLACK_WEBHOOK_URL]):
        print('ERRO: Variáveis de ambiente não configuradas!')
        print('Certifique-se de que JIRA_EMAIL, JIRA_API_TOKEN e SLACK_WEBHOOK_URL estão definidas.')
        sys.exit(1)
    
    # Pega modo dos argumentos (default: daily)
    mode = 'daily'
    if len(sys.argv) > 1 and sys.argv[1] == '--mode':
        if len(sys.argv) > 2:
            mode = sys.argv[2]
    
    print(f'Executando em modo: {mode}')
    
    # Pega range de datas
    start_date, end_date, title = get_date_range(mode)
    
    # Busca issues do Jira
    issues = get_jira_issues(start_date, end_date)
    print(f'Encontradas {len(issues)} issues no período de {start_date} até {end_date}')
    
    # Formata e envia para o Slack
    slack_message = format_slack_message(issues, title, start_date, end_date)
    send_to_slack(slack_message)
    
    # Envia email
    send_email(issues, title, start_date, end_date)

if __name__ == '__main__':
    main()#!/usr/bin/env python3
"""
PMO Bot - Jira para Slack
Envia relatórios automáticos do Jira para o Slack
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from base64 import b64encode
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configurações da API Jira
JIRA_EMAIL = os.environ.get('JIRA_EMAIL')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN')
JIRA_DOMAIN = 'ybymartech.atlassian.net'
JIRA_URL = f'https://{JIRA_DOMAIN}/rest/api/3'

# Slack Webhook
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')

# Email Configuration
EMAIL_SENDER = os.environ.get('EMAIL_SENDER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_RECIPIENTS = os.environ.get('EMAIL_RECIPIENTS', '').split(',')

def get_date_range(mode='daily'):
    """Retorna o range de datas baseado no modo"""
    today = datetime.now()
    
    if mode == 'weekly':
        # Últimos 7 dias
        start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        return start_date, end_date, '📅 Relatório Semanal PMO'
    else:  # daily
        # Hoje
        start_date = today.strftime('%Y-%m-%d')
        end_date = start_date
        hour = today.hour
        
        if hour < 12:
            return start_date, end_date, '☀️ Dashboard Diário PMO - Manhã'
        else:
            return start_date, end_date, '🌆 Dashboard Diário PMO - Tarde'

def get_jira_issues(start_date, end_date):
    """Busca issues do Jira no período especificado"""
    
    # Credenciais encodadas em Base64
    credentials = b64encode(f'{JIRA_EMAIL}:{JIRA_API_TOKEN}'.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/json'
    }
    
    # JQL Query para buscar issues atualizadas no período
    jql = f'updated >= "{start_date}" AND updated <= "{end_date}" ORDER BY updated DESC'
    
    params = {
        'jql': jql,
        'maxResults': 100,
        'fields': 'summary,status,assignee,priority,created,updated'
    }
    
    try:
        response = requests.get(f'{JIRA_URL}/search', headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('issues', [])
    except Exception as e:
        print(f'Erro ao buscar issues: {e}')
        return []

def format_slack_message(issues, title, start_date, end_date):
    """Formata mensagem para o Slack"""
    
    # Contadores por status
    status_count = {}
    for issue in issues:
        status = issue['fields']['status']['name']
        status_count[status] = status_count.get(status, 0) + 1
    
    # Monta a mensagem
    blocks = [
        {
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': title
            }
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f'*Período:* {start_date} até {end_date}\n*Total de issues atualizadas:* {len(issues)}'
            }
        },
        {
            'type': 'divider'
        }
    ]
    
    # Adiciona resumo por status
    if status_count:
        status_text = '*Resumo por Status:*\n'
        for status, count in status_count.items():
            status_emoji = {
                'To Do': '📄',
                'In Progress': '🛠️',
                'Done': '✅',
                'Blocked': '🚫'
            }.get(status, '📌')
            status_text += f'{status_emoji} {status}: {count}\n'
        
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': status_text
            }
        })
    
    # Lista últimas 5 issues
    if issues:
        blocks.append({
            'type': 'divider'
        })
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': '*Últimas issues atualizadas:*'
            }
        })
        
        for issue in issues[:5]:
            key = issue['key']
            summary = issue['fields']['summary']
            status = issue['fields']['status']['name']
            assignee = issue['fields'].get('assignee')
            assignee_name = assignee['displayName'] if assignee else 'Não atribuído'
            
            issue_url = f'https://{JIRA_DOMAIN}/browse/{key}'
            
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f'*<{issue_url}|{key}>* - {summary}\n*Status:* {status} | *Responsável:* {assignee_name}'
                }
            })
    
    return {'blocks': blocks}

def send_to_slack(message):
    """Envia mensagem para o Slack"""
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message)
        response.raise_for_status()
        print('Mensagem enviada para o Slack com sucesso!')
        return True
    except Exception as e:
        print(f'Erro ao enviar mensagem para o Slack: {e}')
        return False

def send_email(issues, title, start_date, end_date):
        """Envia relatório por email"""
        if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECIPIENTS:
                    print('Email não configurado. Pulando envio.')
                    return False

    try:
                # Criar mensagem de email em HTML
                msg = MIMEMultipart('alternative')
                msg['Subject'] = title
                msg['From'] = EMAIL_SENDER
                msg['To'] = ', '.join([r.strip() for r in EMAIL_RECIPIENTS if r.strip()])

        # Construir corpo do email em HTML
        html_body = f"""
                <html>
                            <body style='font-family: Arial, sans-serif;'>
                                            <h2>{title}</h2>
                                                            <p><strong>Período:</strong> {start_date} até {end_date}</p>
                                                                            <p><strong>Total de issues:</strong> {len(issues)}</p>
                                                                                        </body>
                                                                                                </html>
                                                                                                        """

        # Anexar corpo HTML
        part = MIMEText(html_body, 'html')
        msg.attach(part)

        # Conectar ao servidor SMTP e enviar
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                        server.sendmail(EMAIL_SENDER, [r.strip() for r in EMAIL_RECIPIENTS if r.strip()], msg.as_string())
                    print(f'Email enviado com sucesso para {len([r.strip() for r in EMAIL_RECIPIENTS if r.strip()])} destinatário(s)')
        return True

    except Exception as e:
        print(f'Erro ao enviar email: {e}')
        return False

def main():
    """Função principal"""
    
    # Verifica variáveis de ambiente
    if not all([JIRA_EMAIL, JIRA_API_TOKEN, SLACK_WEBHOOK_URL]):
        print('ERRO: Variáveis de ambiente não configuradas!')
        print('Certifique-se de que JIRA_EMAIL, JIRA_API_TOKEN e SLACK_WEBHOOK_URL estão definidas.')
        sys.exit(1)
    
    # Pega modo dos argumentos (default: daily)
    mode = 'daily'
    if len(sys.argv) > 1 and sys.argv[1] == '--mode':
        if len(sys.argv) > 2:
            mode = sys.argv[2]
    
    print(f'Executando em modo: {mode}')
    
    # Obtém range de datas
    start_date, end_date, title = get_date_range(mode)
    
    print(f'Buscando issues de {start_date} até {end_date}...')
    
    # Busca issues
    issues = get_jira_issues(start_date, end_date)
    
    print(f'Encontradas {len(issues)} issues')
    
    # Formata e envia mensagem
    message = format_slack_message(issues, title, start_date, end_date)
    send_to_slack(message)
        send_email(issues, title, start_date, end_date)

if __name__ == '__main__':
    main()
