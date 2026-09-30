# PrimeHarbour Website

A fuller PrimeHarbour build based on the existing PrimePair website files, preserving the existing founder images, story banner, About page styling and background artwork while removing the old News / Journal / Trades / weekly-plan content model.

## Setup

1. Keep your existing `.env` from the old project if you already configured credentials. Do not replace it with `.env.example`.
2. Install dependencies: `pip install -r requirements.txt`
3. Start locally/Codespaces: `python app.py`
4. Health check: `http://127.0.0.1:5000/health`

## Current public model

- Participant profit-share percentage: editable in Admin, default 40%.
- Qualifying loss-refund percentage: editable in Admin, default 40%.
- The examples on the site are calculations only and do not guarantee outcomes.
- Final terms and eligibility are controlled by the applicable written agreement.

## Removed public sections

News, Journal, Trades and the old multi-plan/timeline system are removed from the public UI. Old `/news`, `/journal` and `/trades` paths redirect to the homepage only to prevent broken bookmarks from causing errors.

## Email acknowledgement

Set `GMAIL_SMTP_USER`, `GMAIL_SMTP_APP_PASSWORD` and `AGREEMENT_RECEIVER_EMAIL` in `.env` to enable the generated agreement PNG email.

## Visual updates
- Home hero uses the founder photograph as the main visual instead of a large logo card.
- Homepage old founder story banner section removed; original image assets remain available for the About page.
- Calculator includes USD/INR/EUR/GBP/AED/SGD display options with indicative conversion only.
- Founder photo band is positioned to keep both faces visible.
