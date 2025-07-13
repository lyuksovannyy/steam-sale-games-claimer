import steam
from steam.types.id import AppID
import os
import asyncio
from bs4 import BeautifulSoup

async_exec = False
cooldown = 24 * 60 * 60 # 1d
creds = [
    ("username", "password"),
]

class MyClient(steam.Client):
    def __init__(self, login, **options):
        self.login_ = login
        super().__init__(**options)
    
    async def on_ready(self) -> None:
        with open("./" + self.login_ + ".ref", "w", encoding="utf-8") as f:
            f.write(self.refresh_token)
        print("Logged in as", self.user)
        
        await self.redeem_free_games()
        await self.redeem_free_items()
        
        print("We're done, retrying in:", cooldown, "seconds.")
        await self.close()

    # steam points shop
    async def redeem_free_items(self):
        ...
        
    # games
    async def redeem_free_games(self):
        # fetching free games (100% discount)
        games = await self.parse_free_games()
        if not games:
            print("No games found :(")
            return
        
        for id, title, url in games:
            print(id, "|", title, "->", url)
            data = await self.fetch_game_data(id)
            if not data:
                print("Unable to fetch \"%s\" app." % title)
                continue
            
            name = data["name"]
            appid = data["steam_appid"]
            is_free = data["is_free"]
            is_dlc = data.get("type") == "dlc"
            
            if not is_free: # just to ensure.
                print("\"%s\" isn't free now ???" % name)
                continue
            
            if is_dlc:
                full_game = data["fullgame"]
                
                _name = full_game["name"]
                _appid = int(full_game["appid"])
                
                print("\"%s\" is DLC, trying to redeem main game \"%s\"" % (title, _name))
                
                game_data = await self.fetch_game_data(_appid)
                if not game_data:
                    print("Unable to fetch main game of \"%s\" DLC." % name)
                    continue
                
                is_free = game_data["is_free"]
                
                if not is_free:
                    print("Main game isn't free, skipping...")
                    continue
                    
                await self.redeem_package(game_data["steam_appid"])
                print("Redeemed %s." % _name)
                
            await self.redeem_package(appid)
            print("Redeemed %s." % name)

    async def fetch_game_data(self, id: int) -> dict | None:
        data = (await self.http.get_app(AppID(id), steam.Language.English))[str(id)]
        return data["data"] if data.get("success") else None

    async def fetch_html(self, url, params):
        async with self.http._session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def parse_free_games(self) -> list[tuple[int, str, str]]:
        html = await self.fetch_html(
            "https://store.steampowered.com/search/results/",
            {"sort_by": "Price_ASC", "specials": "1", "cc": "US", "l": "en"},
        )
        
        soup = BeautifulSoup(html, "html.parser")
        free_ids = []
        for row in soup.select("a.search_result_row[data-ds-appid]"):
            title = row.select_one(".search_name .title").text.strip()
            discount_elem = row.select_one(".discount_pct")
            discount = discount_elem and int(discount_elem.text.strip().replace("-", "").replace("%", "")) or 0
            if discount == 100:
                url = row["href"]
                appid = int(row["data-ds-appid"])
                free_ids.append((appid, title, url))
                
        return free_ids

async def job(login, pswd):
    ref_txt = "./" + login + ".ref"
    ref_token = None
    
    # cached ref token
    if not os.path.exists(ref_txt):
        with open(ref_txt, "w", encoding="utf-8") as f:
            ref_token = False
            f.write("")
            
    if ref_token is None:
        with open(ref_txt, "r", encoding="utf-8") as f:
            ref_token = f.read()
    #
    
    login_data = dict( refresh_token = ref_token ) if ref_token else dict( username = login, password = pswd )
    async with asyncio.Timeout(cooldown):
        async with MyClient(login) as client:
            try:
                await client.login(**login_data)
            except ExceptionGroup:
                pass
        
        await asyncio.sleep(cooldown)
        
async def main():
    print("Ready")
    if async_exec:
        jobs = []
        for login, pswd in creds:
            jobs.append(job(login, pswd))
            
        await asyncio.gather(*jobs)
        return
    
    for login, pswd in creds:
        await job(login, pswd)
        await asyncio.sleep(1)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    while True:
        try:
            loop.run_until_complete(main())
        except asyncio.TimeoutError:
            pass
        except KeyboardInterrupt:
            break
