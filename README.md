# 3commas-cyber-bots
> Some 3Commas helper bots (collection will grow over time)

## Why?

I don't want to pay for services if this is not needed, I rather invest it in crypto, and I also want to learn how things work.

## GalaxyScore Bot 'galaxyscore.py'*

## What does it do?

It will monitor LunarCrush's GalaxyScore and use the Top 10 to create pairs for your 3Comma's composite DCA bots to use.

## How does it work?

The GalaxyScore Top 10 coins from LunarCrush are downloaded.

The base pair of each of the specified 3Comma's bots is determined, new pairs are constructed, these are checked against your Blacklist on 3Comma's and the market data of Binance to see if the pairs are valid. (I can add other Exchanges on request)

If this is the case -and the current pair are different- the bot(s) are updated with the new pairs.

Then the galaxyscore bot will sleep for the set interval time, after which it will repeat these steps.


## Binance Setup

-   Create a [Binance account](https://accounts.binance.com/en/register?ref=156153717) (Includes my referral link, I'll be super grateful if you use it).
-   Enable Two-factor Authentication.
-   Create a new API key.
-   Get a stable cryptocurrency to trade with.


## 3Commas Setup

-   Create a [3Commas account](https://3commas.io/?c=tc587527) (Includes my referral link, again I'll be super grateful if you use it).
-   Enable Two-factor Authentication.
-   Connect your 3Commas account with the Binance exchange using the key values created above.
-   Create a new API key with Bot Read and Bot Write permissions, enther these key in config.py
-   Setup a DCA Bot (details will follow)


## LunarCrush Setup

-   Create a [LunarCrush account](https://lunarcrush.com)
-   Create a new API key and enther these key in config.py as well.

## Bot Setup

### Install Python dependencies

Run the following line in the terminal: `pip install -r requirements.txt`.

Or run `setup.sh` script to install everything inside a Python Enviroment, also see below.

### Create user configuration

Create a config file named `config.py` based off `example.config.py`, then add your API keys and settings.

The configuration file contains the following fields:
-   **timeInterval** - time interval in Seconds.
-   **BotIds** - a list of bot id's to manage
-   **ApiKeys** - Your 3Commas API key values.
-   **LunarCrushApiKey** - Your LunarCrush API key value.
-   **NumberOfPairs** - Number of pairs to update your bots with.


### Run the bot

#### Manually
`python3 ./galaxyscore.py`

#### From Python Enviroment
You can use the install script called setup.sh to create this environment.
Simply run it as ./setup.sh and you have the options:
```
usage:
	-i,--install    Install 3commas-cyber-bots from scratch
	-u,--update     Command git pull to update.
```
It creates a .env python enviroment to install the requirements in, and you can run the scripts from there without cluttering your machine.

Before running any of the scripts manually enter the virtual environment first
```
cd 3commas-cyber-bots
source .env/bin/activate
```
#### Automatically

Example service file 3commas-galaxyscore-bot.service, you need to edit the paths inside to reflect your install..
```
sudo cp 3commas-galaxyscore-bot.service /etc/systemd/system/
sudo systemd start 3commas-galaxyscore-bot.service
```

### Example output
```
3Commas GalaxyScore bot. Started at Tuesday 21:53:34 12-10-2021.
Fetched Binance market data OK
1695 symbols loaded from Binance market
Fetched LunarCrush Top X GalaxyScore OK
Fetched 3Commas pairs blacklist OK
51 pairs loaded from 3Commas blacklist
Updating the 3Commas bot(s)
BUSD_USDT pair is not valid on Binance's market, skipping.
BUSD_NKN pair is not valid on Binance's market, skipping.
BUSD_HERO3 pair is not valid on Binance's market, skipping.
BUSD_STRIKE pair is not valid on Binance's market, skipping.
BUSD_FLOKI pair is not valid on Binance's market, skipping.
BUSD_YOOSHI pair is not valid on Binance's market, skipping.
BUSD_DAG pair is not valid on Binance's market, skipping.
BUSD_BCN pair is not valid on Binance's market, skipping.
BUSD_100X pair is not valid on Binance's market, skipping.
BUSD_KDA pair is not valid on Binance's market, skipping.
BUSD_XPR pair is not valid on Binance's market, skipping.
BUSD_BELT pair is not valid on Binance's market, skipping.
BUSD_HANU pair is not valid on Binance's market, skipping.
BUSD_ORION pair is not valid on Binance's market, skipping.
BUSD_LEOS pair is not valid on Binance's market, skipping.
BUSD_TRAVA pair is not valid on Binance's market, skipping.
BUSD_CAKE pair is on your 3Commas blacklist, skipping.
BUSD_DG pair is not valid on Binance's market, skipping.
BUSD_XYO pair is not valid on Binance's market, skipping.
BUSD_SLIM pair is not valid on Binance's market, skipping.
BUSD_POOCOIN pair is not valid on Binance's market, skipping.
BUSD_OHM pair is not valid on Binance's market, skipping.
BUSD_APYS pair is not valid on Binance's market, skipping.
BUSD_AIRT  pair is not valid on Binance's market, skipping.
Bot named 'BUSD Bull Long Bot GalaxyScore' with id 123456 updated to use pairs ['BUSD_DOT', 'BUSD_XTZ',
'BUSD_SOL', 'BUSD_HBAR', 'BUSD_ATOM', 'BUSD_CELR', 'BUSD_ALGO', 'BUSD_POLS', 'BUSD_RAY', 'BUSD_MBOX']
Next bot(s) update in 3600 Seconds at Tuesday 22:53:40 12-10-2021.
```

### TODO
- Download and check more top coins if there are too few because left if there are blacklisted or non valid ones for Binance to keep the minimum.
- Create a real config file
- Add notifications
- Better error handling
- Implement debug information

### Debugging

For now edit this line in `galaxyscore.py` to enable debug output:
```
logging.basicConfig(level=logging.ERROR)
```
to this:
```
logging.basicConfig(level=logging.DEBUG)
```

## Disclaimer

This project is for informational purposes only. You should not construe any
such information or other material as legal, tax, investment, financial, or
other advice. Nothing contained here constitutes a solicitation, recommendation,
endorsement, or offer by me or any third party service provider to buy or sell
any securities or other financial instruments in this or in any other
jurisdiction in which such solicitation or offer would be unlawful under the
securities laws of such jurisdiction.

If you plan to use real money, USE AT YOUR OWN RISK.

Under no circumstances will I be held responsible or liable in any way for any
claims, damages, losses, expenses, costs, or liabilities whatsoever, including,
without limitation, any direct or indirect damages for loss of profits.
