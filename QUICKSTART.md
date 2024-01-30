# Deployment Quickstart

## Prerequisites

Create an account on the following services and collect the relevant access credentials:

- reddit (REDDIT_USERNAME, REDDIT_CLIENT_ID, REDDIT_PASSWORD)
- OpenAI (OPENAI_API_KEY)
- ngrok (NGROK_TOKEN)
- Langchain?

Notes:
* Reddit app needs to be registered as a script (not as a web app)

### Server setup

Access a Lambda VM where to deploy the newsy app.  

Clone the Newsy repository from GitHub:
```bash
git clone https://github.com/LambdaLabsML/newsy
```

Create a Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install newsy dependencies
```bash
pip install wheel
pip install -r requirements.txt 
```

Setup ngrok to expose the newsy server:

Install ngrok
```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && echo "deb https://ngrok-agent.s3.amazonaws.com buster main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list && sudo apt update && sudo apt install ngrok
```

Connect your ngrok account:
```bash
ngrok config add-authtoken ${NGROK_TOKEN}
```

Expose webserver running on vm in a new Screen session:

Start a Screen session:
```bash
screen -S ngrok_session
```
To detach from the screen session and keep it running in the background, press Ctrl+A followed by D

Run ngrok:
```
ngrok http http://localhost:8080
```

You should see info like this:
```
ngrok                                                               (Ctrl+C to quit)
                                                                                    
Build better APIs with ngrok. Early access: ngrok.com/early-access                  
                                                                                    
Session Status                online                                                
Account                       <your email address> (Plan: Free)                        
Version                       3.5.0                                                 
Region                        United States (California) (us-cal-1)                 
Latency                       20ms                                                  
Web Interface                 http://127.0.0.1:4040                                 
Forwarding                    https://d3d3-129-146-111-221.ngrok-free.app -> http://
                                                                                    
Connections                   ttl     opn     rt1     rt5     p50     p90           
                              0       0       0.00    0.00    0.00    0.00
```

Retrieve the forwarding address and update `slack-app-manifest.yaml` accordingly. It should look like this:
```
...
settings:
  event_subscriptions:
    request_url: https://d3d3-129-146-111-221.ngrok-free.app/slack/events/lambda-docs-bot
...
```
### Slack setup

Create a new slack app in your workspace: https://api.slack.com/apps/new
Use the config in `slack-app-manifest.yaml` (with the updated `request_url` value).

Collect `SLACK_APP_TOKEN` and `SLACK_BOT_TOKEN` for next steps:
1. Head to https://api.slack.com/apps
2. Create an app level token with all permissions (should start with `xapp-...`)
3. Get the app Bot token from the 'OAuth & Permissions' section (should start with `xbot-...`


## Set Environment Variables

Create a file with the environment variables

`.env_vars`
```
export SLACK_APP_TOKEN=...
export SLACK_BOT_TOKEN=...
export REDDIT_CLIENT_ID=...
export REDDIT_CLIENT_SECRET=...
export REDDIT_PASSWORD=...
export REDDIT_USERNAME=...
export OPENAI_API_KEY=...
```

Set the environment variables:
```bash
source .env_vars
```


### Run Newsy

Start a Screen session:
```bash
screen -S newsy_session
```
To detach from the screen session and keep it running in the background, press Ctrl+A followed by D


Run newsy app:
```bash
python3 app.py
```

### Test deployment

Head to the slack channel where the new `newsy` app deployment has been made.
Prompt newsy:

```
@newsy news
```
