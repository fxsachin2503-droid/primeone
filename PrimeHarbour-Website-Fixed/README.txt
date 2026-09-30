PrimeHarbour Discord Integration

Use these files to add the new Discord guide page to your existing project.

Included:
- app.py — your supplied app.py with /discord route added
- templates/base.html — navigation updated with DISCORD in desktop and mobile menus
- templates/discord.html — premium Discord/process/rules page
- static/images/ph-discord-server.png
- static/images/ph-discord-welcome.png
- static/images/ph-discord-server-alt.png
- static/images/ph-discord-announcement.png

Not included:
- data.json
- .env
- your existing CSS/assets

Keep your existing data.json and .env.

After copying into your project:
  python -m py_compile app.py
  python app.py

Page:
  /discord

Note:
The included images are guide/promotional visuals, not live captures of Discord UI.
Replace them with your actual server screenshots using the same filenames if you want true click-by-click screenshots.
