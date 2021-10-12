# 3commas-cyber-bots
> Some 3Commas helper bots (collection will grow over time)

## Why?

I don't want to pay for services if this is not needed, I rather invest it in crypto, and I also want to learn how things work.

## galaxyscore.py

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
-   Create a new API key with Bot Read and Bot Write permissions, enther these key in config.py
-   Setup a DCA Bot (details will follow)


## LunarCrush Setup

-   Create a [LunarCrush account](https://lunarcrush.com)
-   Create a new API key and enther these key in config.py as well.

## Bot Setup

### Install Python dependencies

Run the following line in the terminal: `pip install -r requirements.txt`.
Or run `setup.sh` to install everything inside a Python Enviroment.

### Create user configuration

Create a config file named `config.py` based off `example.config.py`, then add your API keys and settings.

**The configuration file consists of the following fields:**
-   **timeInterval** - time interval in Seconds.
-   **BotIds** - a list of bot id's to manage
-   **ApiKeys** - Your 3Commas API key values.
-   **LunarCrushApiKey** - Your LunarCrush API key value.


### Run the bot

`python3 ./galaxyscore.py` or check out the service file.

### TODO
- Create a real config file
- Add notifications
- Better error handling
- Implement debug information

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
