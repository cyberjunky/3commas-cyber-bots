[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/) [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)

# 3commas-cyber-bots
> Some 3Commas helper bots (collection will grow over time)

## Why?

I don't want to pay for services if this is not needed, I rather invest it in crypto, and I also want to learn how things work.

## GalaxyScore bot helper 'galaxyscore.py'*

## What does it do?

It will monitor LunarCrush's GalaxyScores and use the Top X to create pairs for your 3Comma's composite DCA bots to use.

## How does it work?

The GalaxyScore Top 10 coins from LunarCrush are downloaded.
And the base pair of each of the specified 3Comma's bots is determined, from this new pairs are constructed, these are checked against your Blacklist on 3Comma's and the market data of Binance or FTX to see if the pairs are valid. (I can add other Exchanges on request)

If this is the case -and the current pair are different- the bot(s) are updated with the new pairs.

Then the bot helper will sleep for the set interval time, after which it will repeat these steps.


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
Support the Project
-   Create a [LunarCrush account](https://lunarcrush.com)
-   Create a new API key and enther these key in config.py as well.

## Bot Setup

### Install Python dependencies

Run the following line in the terminal: `pip install -r requirements.txt`.

Or run `setup.sh` script to install everything inside a Python Enviroment, also see below.

### Create user configuration

If your run galaxyscore for the first time it will create default config file named `config.ini` edit it with the information below.

The configuration file contains the following sections and fields:
-   **[main]**
-   **debug** - set to true to enable debug logging to file. (default is False)
-   **[galaxyscore]**
-   **timeinterval** - update timeinterval in Seconds. (default is 3600)
-   **numberofpairs** - number of pairs to update your bots with. (default is 10)
-   **3c-apikey** - Your 3Commas API key value.
-   **3c-apisecret** - Your 3Commas API key secret value.
-   **lc-apikey** - Your LunarCrush API key value.
-   **botids** - a list of bot id's to manage separated with commas
-   **notifications** - set to true to enable notifications. (default = False)
-   **notify-urls** - one or a list of apprise notify urls, each in " " seperated with commas. See [Apprise website](https://github.com/caronc/apprise) for more information.


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
2021-10-13 18:08:52,369 INFO - 3Commas GalaxyScore bot helper. Started at Wednesday 18:08:52 13-10-2021
2021-10-13 18:08:52,370 INFO - Loaded configuration from 'config.ini'
2021-10-13 18:08:52,370 INFO - Notifications are disabled
2021-10-13 18:08:53,551 INFO - Fetched Binance market data OK (1695 pairs)
2021-10-13 18:08:53,551 INFO - 1695 symbols loaded from Binance market
2021-10-13 18:08:53,637 INFO - Fetched FTX market data OK (473 pairs)
2021-10-13 18:08:55,177 INFO - Fetched LunarCrush Top X GalaxyScore OK (50 coins)
2021-10-13 18:08:55,278 INFO - Fetched 3Commas pairs blacklist OK (52 pairs)
2021-10-13 18:08:55,566 INFO - Finding the best pairs for Binance exchange
2021-10-13 18:08:55,568 INFO - Updating your 3Commas bot(s)
2021-10-13 18:08:55,713 INFO - Bot 'BUSD Bull Long Bot TTP - 751 - GalaxyScore' updated with these pairs:
2021-10-13 18:08:55,713 INFO - ['BUSD_VET', 'BUSD_LTC', 'BUSD_RVN', 'BUSD_QNT', 'BUSD_XLM', 'BUSD_DOGE', 
'BUSD_OMG', 'BUSD_SFP', 'BUSD_RAY', 'BUSD_DGB']
2021-10-13 18:08:55,713 INFO - Next update in 1800 Seconds at 18:38:55

```

### TODO
- You tell me

### Debugging

For now edit this line in `galaxyscore.py` to enable debug output:
```
logging.basicConfig(level=logging.ERROR)
```
to this:
```
logging.basicConfig(level=logging.DEBUG)
```

## Support the Project
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/cyberjunkynl/)

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
