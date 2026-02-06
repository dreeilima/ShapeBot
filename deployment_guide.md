# Guia de Deploy: ShapeBot no Koyeb 🚀☁️

Siga estes passos para colocar seu bot em produção.

## 1. Preparação (Local)
1.  Certifique-se de que seu código está em um repositório no **GitHub** (Público ou Privado).
2.  O `Dockerfile` e os ajustes no `run.py` que eu fiz já estão prontos para o Koyeb.

## 2. Configuração no Koyeb
1.  Vá para o [Painel do Koyeb](https://app.koyeb.com/).
2.  Clique em **"Create Service"**.
3.  Selecione **GitHub** como fonte e escolha seu repositório.
4.  **Builder**: Selecione **"Docker"**. Ele vai ler automaticamente o arquivo `Dockerfile` que criamos.
5.  **Environment Variables**: Clique em "Add Variable" e adicione:
    - `TELEGRAM_TOKEN`: (Seu token do BotFather)
    - `GEMINI_API_KEY`: (Sua nova chave da Google AI)
    - `DATABASE_URL`: URL do banco PostgreSQL (Veja passo 3 abaixo).
    - `DASHBOARD_URL`: A URL pública do seu app no Koyeb (Ex: `https://seu-app.koyeb.app`).
6.  **Expose Port**: Defina como **8001** (ou deixe em branco se ele detectar o `EXPOSE` do Docker).

## 3. Banco de Dados (PostgreSQL)
Recomendo criar um banco no próprio Koyeb ou usar o **Neon.tech** (gratuito e excelente).
- Copie a `DATABASE_URL` do banco criado.
- Cole nas variáveis de ambiente do serviço do bot.

## 4. Finalizando
1.  Clique em **"Deploy"**.
2.  O Koyeb vai buildar a imagem Docker e subir o bot.
3.  Quando terminar, ele fornecerá uma URL pública (ex: `https://shapebot-seu-nome.koyeb.app`).
4.  **DICA**: Essa URL é o seu novo Dashboard!

## FAQ ❓
- **Como ver os logs?** No painel da Koyeb, tem uma aba "Runtime Logs".
- **O bot parou?** Verifique se o `DATABASE_URL` está correto e se o banco permite conexões externas.
