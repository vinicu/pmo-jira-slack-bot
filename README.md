# pmo-jira-slack-bot
Automação PMO - Jira para Slack com GitHub Actions

## Configuraçao de Variáveis de Ambiente

Configure as seguintes variáveis de ambiente no GitHub Actions ou localmente:

### Jira Configuration
- `JIRA_EMAIL`: Seu email do Jira
- - `JIRA_API_TOKEN`: Token de API do Jira
 
  - ### Slack Configuration
  - - `SLACK_WEBHOOK_URL`: Webhook URL do Slack para envio de mensagens
   
    - ### Email Configuration (Gmail)
    - - `EMAIL_SENDER`: Seu email do Gmail (ex: seu-email@gmail.com)
      - - `EMAIL_PASSWORD`: Senha de aplicativo do Gmail (não a senha normal)
        - - `EMAIL_RECIPIENTS`: Emails dos destinatários separados por vírgula (ex: email1@gmail.com,email2@gmail.com)
         
          - #### Como gerar a senha de aplicativo do Gmail:
          - 1. Vá para https://myaccount.google.com
            2. 2. Clique em "Segurança" no menu lateral
               3. 3. Procure por "Senhas de app" e gere uma senha para "App customizado" (Python)
                  4. 4. Copie a senha gerada e use como `EMAIL_PASSWORD`
