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

JIRA_EMAIL = os.environ.get('JIRA_EMAIL')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN')
JIRA_DOMAIN = 'ybymartech.atlassian.net'
JIRA_URL = f'https://{JIRA_DOMAIN}/rest/api/3'
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')
EMAIL_SENDER = os.environ.get('EMAIL_SENDER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'gmail')
EMAIL_RECIPIENTS = os.environ.get('EMAIL_RECIPIENTS', '').split(',')

def get_date_range(mode='daily'):
    today = datetime.now()
    if mode == 'weekly':
        start = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        end = today.strftime('%Y-%m-%d')
        title = '📅 Relatório Semanal PMO'
    else:
        start = today.strftime('%Y-%m-%d')
        end = start
        hour = today.hour
        title = '☀️ Dashboard Diário PMO - Manhã' if hour < 12 else '🌆 Dashboard Diário PMO - Tarde'
    return start, end, title

def get_jira_issues(start_date, end_date):
    credentials = b64encode(f'{JIRA_EMAIL}:{JIRA_API_TOKEN}'.encode()).decode()
    headers = {'Authorization': f'Basic {credentials}', 'Content-Type': 'application/json'}
    jql = f'updated >= "{start_date}" AND updated <= "{end_date}" ORDER BY updated DESC'
    params = {'jql': jql, 'maxResults': 100, 'fields': 'summary,status,assignee,priority,created,updated'}
    try:
        response = requests.get(f'{JIRA_URL}/search', headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('issues', [])
    except Exception as e:
        print(f'Erro ao buscar issues: {e}')
        return []

def format_slack_message(issues, title, start_date, end_date):
    blocks = [
        {'type': 'header', 'text': {'type': 'plain_text', 'text': title}},
        {'type': 'section', 'text': {'type': 'mrkdwn', 'text': f'*Período:* {start_date} até {end_date}\n*Total:* {len(issues)} issues'}}
    ]
    if issues:
        blocks.append({'type': 'divider'})
        for issue in issues[:5]:
            key = issue['key']
            summary = issue['fields']['summary']
            status = issue['fields']['status']['name']
            assignee = issue['fields'].get('assignee')
            assignee_name = assignee['displayName'] if assignee else 'Não atribuído'
            url = f'https://{JIRA_DOMAIN}/browse/{key}'
            blocks.append({'type': 'section', 'text': {'type': 'mrkdwn', 'text': f'*<{url}|{key}>* - {summary}\nStatus: {status} | Responsável: {assignee_name}'}})
    return {'blocks': blocks}

def send_to_slack(message):
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=message)
        response.raise_for_status()
        print('Mensagem enviada para o Slack com sucesso!')
        return True
    except Exception as e:
        print(f'Erro ao enviar para Slack: {e}')
        return False

def send_email(issues, title, start_date, end_date):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECIPIENTS:
        print('Email não configurado. Pulando envio.')
        return False
    try:
        recipients_list = [r.strip() for r in EMAIL_RECIPIENTS if r.strip()]
        msg = MIMEMultipart()
        msg['Subject'] = title
        msg['From'] = EMAIL_SENDER
        msg['To'] = ', '.join(recipients_list)
        body = f"""Relatório PMO\n\nPeríodo: {start_date} até {end_date}\nTotal de issues: {len(issues)}\n\n"""
        if issues:
            body += "Últimas issues:\n\n"
            for issue in issues[:10]:
                key = issue['key']
                summary = issue['fields']['summary']
                status = issue['fields']['status']['name']
                assignee = issue['fields'].get('assignee')
                name = assignee['displayName'] if assignee else 'Não atribuído'
                url = f'https://{JIRA_DOMAIN}/browse/{key}'
                body += f"{key} - {summary}\nStatus: {status} | Responsável: {name}\nLink: {url}\n\n"
        msg.attach(MIMEText(body, 'plain'))
        if EMAIL_PROVIDER.lower() == 'outlook':
            with smtplib.SMTP('smtp.office365.com', 587) as server:
                server.starttls()
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, recipients_list, msg.as_string())
        else:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.sendmail(EMAIL_SENDER, recipients_list, msg.as_string())
        print(f'Email enviado para {len(recipients_list)} destinatário(s)!')
        return True
    except Exception as e:
        print(f'Erro ao enviar email: {e}')
        return False

def main():
    if not all([JIRA_EMAIL, JIRA_API_TOKEN, SLACK_WEBHOOK_URL]):
        print('ERRO: Variáveis de ambiente não configuradas!')
        sys.exit(1)
    mode = 'daily'
    if len(sys.argv) > 1 and sys.argv[1] == '--mode' and len(sys.argv) > 2:
        mode = sys.argv[2]
    print(f'Executando em modo: {mode}')
    start_date, end_date, title = get_date_range(mode)
    issues = get_jira_issues(start_date, end_date)
    print(f'Encontradas {len(issues)} issues no período de {start_date} até {end_date}')
    slack_message = format_slack_message(issues, title, start_date, end_date)
    send_to_slack(slack_message)
    send_email(issues, title, start_date, end_date)

if __name__ == '__main__':
    main()
