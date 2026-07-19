# Monitor de Concursos DPU + DPEs (todas as regiões)

Sistema que verifica automaticamente, todos os dias, se alguma Defensoria
Pública (a DPU ou qualquer uma das 27 DPEs estaduais) publicou algo novo
sobre concurso — edital, abertura de inscrições, banca definida etc. — e
te avisa por WhatsApp.

## Como funciona (visão geral)

1. `config.json` tem a lista de 28 sites oficiais (padrão `defensoria.[UF].def.br`
   + `dpu.def.br`) e mais 4 sites agregadores que já compilam notícias de
   todas as regiões em um só lugar.
2. `monitor.py` baixa o texto de cada site, procura por palavras-chave
   ("edital publicado", "inscrições abertas" etc.) e compara com a última
   verificação.
3. Quando encontra algo novo, manda uma mensagem pro seu WhatsApp via
   CallMeBot (gratuito).
4. O GitHub Actions roda esse script uma vez por dia, de graça, sem você
   precisar deixar nada ligado.

## Passo a passo para colocar no ar (uns 15-20 minutos)

### 1. Ativar o CallMeBot (WhatsApp gratuito)
1. Adicione o número **+34 644 59 71 30** aos seus contatos do WhatsApp.
2. Envie para esse contato a mensagem: `I allow callmebot to send me messages`
3. Você vai receber uma resposta com sua **API Key** (um número). Guarde-a.

### 2. Criar o repositório no GitHub
1. Crie uma conta gratuita em https://github.com (se ainda não tiver).
2. Crie um repositório novo, **privado**, com qualquer nome (ex: `monitor-concursos`).
3. Suba estes arquivos para o repositório (pela interface web do GitHub,
   arrastando os arquivos, ou via `git push` se preferir linha de comando).

### 3. Configurar os "Secrets" (dados sensíveis, não ficam expostos no código)
No repositório: **Settings → Secrets and variables → Actions → New repository secret**
Crie dois secrets:
- `TELEFONE_DESTINO` → seu número com DDI e DDD, sem espaços nem símbolos
  (ex: `5581999998888` para um número de Recife)
- `CALLMEBOT_APIKEY` → a API key que você recebeu no passo 1

### 4. Ativar o agendamento automático
1. Vá na aba **Actions** do repositório.
2. Se aparecer um aviso pedindo para habilitar workflows, clique para habilitar.
3. Pronto — a partir daí ele roda sozinho todo dia às 9h (horário de Brasília).
4. Para testar na hora, sem esperar o dia seguinte: aba **Actions** →
   **Monitor de Concursos DPU/DPE** → **Run workflow**.

## Personalização

- **Frequência**: para rodar mais vezes por dia, edite a linha `cron` em
  `.github/workflows/monitor.yml` (ex: `0 */6 * * *` roda a cada 6 horas).
- **Adicionar/corrigir fontes**: edite `config.json` — cada item de
  `fontes_oficiais` é só `{"regiao": "...", "url": "..."}`.
- **Palavras-chave**: ajuste a lista `palavras_chave_gatilho` em `config.json`
  conforme perceber falsos positivos ou termos que estão passando batido.

## Limitações importantes (leia antes de confiar 100% no sistema)

- Alguns sites oficiais de Defensoria têm estrutura de página que muda
  bastante entre estados — o monitor detecta **mudança de texto na home**,
  o que é um bom sinal de alerta, mas não garante que 100% dos editais
  serão pegos automaticamente logo na home. Por isso o `config.json` já
  inclui 4 agregadores (Estratégia, Gran Cursos, Magistrar, ANADEP) que
  compilam notícias de todos os estados e tendem a ser mais confiáveis
  para pegar a notícia rápido.
- CallMeBot é um serviço gratuito não-oficial e pode ocasionalmente
  atrasar ou falhar mensagens. Se isso incomodar, o próximo passo natural
  é migrar para Z-API (pago, mais estável) — o código já está estruturado
  para isso (só trocar a função `enviar_whatsapp`).
- Este sistema, do jeito que está, é para **uso pessoal** (um único
  destinatário). Se depois você quiser abrir para outras pessoas se
  cadastrarem sozinhas, aí sim vale a pena migrar para um banco de dados
  real (Supabase/Postgres) com formulário de cadastro — posso montar isso
  quando for a hora.
